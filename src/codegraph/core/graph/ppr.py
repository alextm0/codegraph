"""GDS projection and Personalized PageRank over the code graph."""

import logging
from dataclasses import dataclass

from neo4j import Driver
from graphdatascience import GraphDataScience
from graphdatascience.graph.graph_object import Graph

logger = logging.getLogger(__name__)

_PROJECTION_NAME = "codegraph"


@dataclass(frozen=True)
class PPRConfig:
    """Parameters controlling Personalized PageRank execution.

    Attributes:
        damping_factor: Probability of following a graph edge vs. teleporting back to a seed node.
            Higher values weight graph structure more heavily.
        max_iterations: Upper bound on the number of convergence iterations.
        tolerance: Convergence threshold — iteration stops when score delta falls below this.
        top_k: Maximum number of ranked results to return.
    """

    damping_factor: float = 0.85
    max_iterations: int = 20
    tolerance: float = 1e-7
    top_k: int = 20


@dataclass(frozen=True)
class PPRResult:
    """A single ranked node returned by PPR."""

    qualified_name: str
    name: str
    label: str
    file_path: str
    score: float
    line_start: int = 0
    line_end: int = 0


def create_gds_client(driver: Driver) -> GraphDataScience:
    """Create and return a GDS client backed by the given driver."""
    gds = GraphDataScience.from_neo4j_driver(driver)
    logger.debug("GDS client created")
    return gds


def project_graph(gds: GraphDataScience) -> Graph:
    """Create an in-memory GDS projection covering all node/edge types.

    Uses UNDIRECTED orientation with relationship weight property.
    Returns the GDS Graph object (supports node_count(), relationship_count()).
    """
    node_spec = ["File", "Function", "Class", "Method"]
    relationship_spec = {
        "CONTAINS": {"orientation": "UNDIRECTED", "properties": "weight"},
        "CALLS": {"orientation": "UNDIRECTED", "properties": "weight"},
        "IMPORTS": {"orientation": "UNDIRECTED", "properties": "weight"},
        "INHERITS_FROM": {"orientation": "UNDIRECTED", "properties": "weight"},
    }

    # Drop any existing projection with the same name
    drop_projection(gds)

    create_result = gds.graph.project(_PROJECTION_NAME, node_spec, relationship_spec)
    # GraphCreateResult is a NamedTuple(graph, result); .graph is the Graph object.
    projection = create_result.graph
    logger.info(
        "GDS projection '%s' created: %d nodes, %d relationships",
        _PROJECTION_NAME,
        projection.node_count(),
        projection.relationship_count(),
    )
    return projection


def drop_projection(gds: GraphDataScience) -> bool:
    """Drop the in-memory projection if it exists. Returns True if it existed."""
    try:
        exists_result = gds.graph.exists(_PROJECTION_NAME)
        exists = exists_result["exists"]
        if exists:
            graph = gds.graph.get(_PROJECTION_NAME)
            gds.graph.drop(graph)
            logger.debug("Dropped GDS projection '%s'", _PROJECTION_NAME)
            return True
        return False
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.debug("drop_projection: expected error (e.g., missing key/projection): %s", exc)
        return False
    except Exception as exc:
        logger.error("drop_projection: unexpected error: %s", exc)
        raise


def run_ppr(
    gds: GraphDataScience,
    driver: Driver,
    seed_names: list[str],
    config: PPRConfig | None = None,
) -> list[PPRResult]:
    """Run Personalized PageRank seeded from nodes whose name matches seed_names.

    Returns top-k results sorted by descending score.
    The driver is used for Cypher lookups (seed node IDs and result properties).
    """
    if config is None:
        config = PPRConfig()

    seed_ids = _resolve_seed_ids(driver, seed_names)
    if not seed_ids:
        logger.warning("PPR: no seed nodes found for names %s", seed_names)
        return []

    return run_ppr_from_node_ids(gds, driver, seed_ids, config)


def run_ppr_from_node_ids(
    gds: GraphDataScience,
    driver: Driver,
    seed_ids: list[int],
    config: PPRConfig,
) -> list[PPRResult]:
    """Run PPR from explicit internal node IDs and return ranked PPRResult list."""
    projection = gds.graph.get(_PROJECTION_NAME)

    result_df = gds.pageRank.stream(
        projection,
        maxIterations=config.max_iterations,
        dampingFactor=config.damping_factor,
        tolerance=config.tolerance,
        sourceNodes=seed_ids,
        relationshipWeightProperty="weight",
    )

    # result_df has columns: nodeId, score
    top_rows = result_df.sort_values("score", ascending=False).head(config.top_k)

    # Batch-fetch all node properties in one query instead of N individual round-trips.
    node_ids = [int(row["nodeId"]) for _, row in top_rows.iterrows()]
    scores = {int(row["nodeId"]): float(row["score"]) for _, row in top_rows.iterrows()}
    props_by_id = _fetch_all_node_properties(driver, node_ids)

    results: list[PPRResult] = []
    for node_id in node_ids:
        props = props_by_id.get(node_id)
        if props:
            results.append(
                PPRResult(
                    qualified_name=props.get("qualified_name", ""),
                    name=props.get("name", ""),
                    label=props.get("label", ""),
                    file_path=props.get("file_path", ""),
                    score=scores[node_id],
                    line_start=props.get("line_start", 0),
                    line_end=props.get("line_end", 0),
                )
            )

    logger.info("PPR returned %d results (top_k=%d)", len(results), config.top_k)
    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_seed_ids(driver: Driver, seed_names: list[str]) -> list[int]:
    """Query Neo4j for the internal node IDs of all nodes matching seed_names.

    Returns every matching node ID so that PPR seeds on all of them,
    rather than picking an arbitrary single match per name.
    """
    ids: list[int] = []
    with driver.session() as session:
        for name in seed_names:
            result = session.run(
                """
                MATCH (n)
                WHERE n.name = $name
                   OR n.qualified_name = $name
                   OR (n:Method AND (n.class_name + "." + n.name) = $name)
                RETURN id(n) AS nid
                """,
                name=name,
            )
            records = list(result)
            if records:
                for record in records:
                    ids.append(record["nid"])
            else:
                logger.warning("PPR seed not found: '%s'", name)
    return ids


def _fetch_all_node_properties(driver: Driver, node_ids: list[int]) -> dict[int, dict]:
    """Batch-fetch name, qualified_name, label, file_path for all given node IDs.

    Uses a single UNWIND query instead of one round-trip per node.
    Returns a dict mapping nodeId -> property dict.

    # TODO: migrate to elementId() for Neo4j 6.x (id() is deprecated in 5.x but still functional).
    """
    if not node_ids:
        return {}
    props_by_id: dict[int, dict] = {}
    with driver.session() as session:
        result = session.run(
            """
            UNWIND $ids AS nid
            MATCH (n) WHERE id(n) = nid
            RETURN id(n) AS node_id,
                   n.qualified_name AS qualified_name,
                   n.name AS name,
                   labels(n)[0] AS label,
                   n.file_path AS file_path,
                   coalesce(n.line_number, 0) AS line_start,
                   coalesce(n.end_line, 0) AS line_end
            """,
            ids=node_ids,
        )
        for record in result:
            props_by_id[record["node_id"]] = {
                "qualified_name": record["qualified_name"] or "",
                "name": record["name"] or "",
                "label": record["label"] or "",
                "file_path": record["file_path"] or "",
                "line_start": record["line_start"] or 0,
                "line_end": record["line_end"] or 0,
            }
    return props_by_id
