"""Cypher query functions for the code graph.

Design notes:
- Most functions are read-only (MATCH only). Exception: delete_file_entities runs DETACH DELETE
  and requires a writable driver; callers should obtain one from DatabaseManager.
- driver defaults to None; pass one explicitly in tests or accept the singleton from DatabaseManager.
- To add a new node label: update any label-filtering queries (e.g. find_dead_code, count_nodes_by_label)
  to include the new label, and add a corresponding result dataclass if needed.
"""

import logging
from dataclasses import dataclass
from typing import Any

from neo4j import Driver
from codegraph.core.graph.database import get_database_manager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeInfo:
    """Structured result for a single graph node."""

    qualified_name: str
    name: str
    label: str
    file_path: str


@dataclass(frozen=True)
class NodeInfoWithRel(NodeInfo):
    """NodeInfo extended with the relationship type connecting it to the queried entity."""

    relationship_type: str = ""


@dataclass(frozen=True)
class DeadCodeNode:
    """A Function or Method node with no incoming CALLS edges."""

    qualified_name: str
    name: str
    label: str
    file_path: str
    line_number: int


def count_nodes_by_label(driver: Driver | None = None) -> dict[str, int]:
    """Return a mapping of node label -> count."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY label"
        )
        return {record["label"]: record["cnt"] for record in result}


def count_edges_by_type(driver: Driver | None = None) -> dict[str, int]:
    """Return a mapping of relationship type -> count."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt ORDER BY rel_type"
        )
        return {record["rel_type"]: record["cnt"] for record in result}


def get_neighbors(
    driver: Driver | None = None, qualified_name: str = ""
) -> list[NodeInfo]:
    """Return all nodes directly connected (in either direction) to the given node."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n {qualified_name: $qname})-[*1]-(neighbor)
            RETURN DISTINCT neighbor.qualified_name AS qualified_name,
                   neighbor.name AS name,
                   labels(neighbor)[0] AS label,
                   neighbor.file_path AS file_path
            ORDER BY qualified_name
            """,
            qname=qualified_name,
        )
        return [_row_to_node_info(r) for r in result]


def get_file_contents(
    driver: Driver | None = None, file_path: str = ""
) -> list[NodeInfo]:
    """Return all entities directly contained in a file."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (f:File {file_path: $file_path})-[:CONTAINS]->(entity)
            RETURN entity.qualified_name AS qualified_name,
                   entity.name AS name,
                   labels(entity)[0] AS label,
                   entity.file_path AS file_path
            ORDER BY qualified_name
            """,
            file_path=file_path,
        )
        return [_row_to_node_info(r) for r in result]


def find_callers(
    driver: Driver | None = None, qualified_name: str = ""
) -> list[NodeInfo]:
    """Return all nodes that call the given node."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (caller)-[:CALLS]->(target {qualified_name: $qname})
            RETURN caller.qualified_name AS qualified_name,
                   caller.name AS name,
                   labels(caller)[0] AS label,
                   caller.file_path AS file_path
            ORDER BY qualified_name
            """,
            qname=qualified_name,
        )
        return [_row_to_node_info(r) for r in result]


def find_callees(
    driver: Driver | None = None, qualified_name: str = ""
) -> list[NodeInfo]:
    """Return all nodes called by the given node."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (caller {qualified_name: $qname})-[:CALLS]->(callee)
            RETURN callee.qualified_name AS qualified_name,
                   callee.name AS name,
                   labels(callee)[0] AS label,
                   callee.file_path AS file_path
            ORDER BY qualified_name
            """,
            qname=qualified_name,
        )
        return [_row_to_node_info(r) for r in result]


def find_node_by_name(driver: Driver | None = None, name: str = "") -> list[NodeInfo]:
    """Return all nodes whose name property matches exactly."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n {name: $name})
            RETURN n.qualified_name AS qualified_name,
                   n.name AS name,
                   labels(n)[0] AS label,
                   n.file_path AS file_path
            ORDER BY qualified_name
            """,
            name=name,
        )
        return [_row_to_node_info(r) for r in result]


def find_node_by_pattern(
    driver: Driver | None = None, pattern: str = ""
) -> list[NodeInfo]:
    """Return all nodes whose name property contains the given pattern (case-insensitive)."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            WHERE n.name CONTAINS $pattern OR n.qualified_name CONTAINS $pattern
            RETURN n.qualified_name AS qualified_name,
                   n.name AS name,
                   labels(n)[0] AS label,
                   n.file_path AS file_path
            ORDER BY qualified_name
            LIMIT 100
            """,
            pattern=pattern,
        )
        return [_row_to_node_info(r) for r in result]


def get_inheritance_chain(
    driver: Driver | None = None, class_qname: str = ""
) -> list[NodeInfo]:
    """Return the full inheritance chain (ancestors) of a class, ordered from immediate parent upward."""
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH p = (cls:Class {qualified_name: $qname})-[:INHERITS_FROM*1..]->(ancestor:Class)
            RETURN ancestor.qualified_name AS qualified_name,
                   ancestor.name AS name,
                   labels(ancestor)[0] AS label,
                   ancestor.file_path AS file_path
            ORDER BY length(p) ASC
            """,
            qname=class_qname,
        )
        return [_row_to_node_info(r) for r in result]


def query_entity_dependencies(
    driver: Driver | None = None,
    entity_name: str = "",
    direction: str = "both",
    depth: int = 1,
) -> list[NodeInfoWithRel]:
    """Return dependency nodes for a code entity.

    Args:
        driver: Active Neo4j driver.
        entity_name: Exact name or qualified_name of the entity to look up.
        direction: One of "upstream" (callers), "downstream" (callees), or "both".
        depth: How many hops to follow. 1 = direct only, 2 = include indirect.

    Returns:
        Deduplicated list of NodeInfoWithRel for all found dependencies.
    """
    if driver is None:
        driver = get_database_manager().get_driver()
    _validate_direction(direction)
    depth = max(1, min(depth, 2))  # clamp to supported range

    # Build the Cypher pattern based on direction.
    # We use a variable-length relationship pattern (:CALLS|IMPORTS*1..depth)
    # to support depth 1 (direct only) and depth 2 (include indirect).
    if direction == "downstream":
        cypher = _downstream_cypher(depth)
    elif direction == "upstream":
        cypher = _upstream_cypher(depth)
    else:  # "both"
        cypher = _both_directions_cypher(depth)

    results: list[NodeInfoWithRel] = []
    with driver.session() as session:
        records = session.run(cypher, name=entity_name)
        for record in records:
            results.append(_row_to_node_info_with_rel(record))

    logger.debug(
        "query_entity_dependencies: found %d nodes for '%s' (direction=%s, depth=%d)",
        len(results),
        entity_name,
        direction,
        depth,
    )
    return results


def find_dead_code(driver: Driver | None = None, limit: int = 50) -> list[DeadCodeNode]:
    """Return Function and Method nodes that have zero incoming CALLS edges.

    These are candidates for dead code — they are never called by any other
    entity in the graph. False positives include public API entry points,
    decorated handlers (e.g. FastAPI routes), and test functions.

    Args:
        driver: Active Neo4j driver.
        limit: Maximum number of results to return.

    Returns:
        List of DeadCodeNode for uncalled Function/Method nodes, sorted by file.
    """
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Function OR n:Method)
              AND NOT ()-[:CALLS]->(n)
            RETURN n.qualified_name AS qualified_name,
                   n.name AS name,
                   labels(n)[0] AS label,
                   n.file_path AS file_path,
                   coalesce(n.line_number, 0) AS line_number
            ORDER BY file_path, qualified_name
            LIMIT $limit
            """,
            limit=limit,
        )
        return [
            DeadCodeNode(
                qualified_name=r["qualified_name"] or "",
                name=r["name"] or "",
                label=r["label"] or "",
                file_path=r["file_path"] or "",
                line_number=r["line_number"] or 0,
            )
            for r in result
        ]


def get_most_connected_files(
    driver: Driver | None = None, limit: int = 10
) -> list[dict]:
    """Return files ranked by number of directly contained entities.

    Useful for understanding which files are the most structurally
    important in the codebase.

    Returns:
        List of dicts with keys "file_path" and "entity_count",
        sorted descending by entity_count.
    """
    if driver is None:
        driver = get_database_manager().get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (f:File)-[:CONTAINS]->(entity)
            WITH f.file_path AS file_path, count(entity) AS entity_count
            ORDER BY entity_count DESC
            LIMIT $limit
            RETURN file_path, entity_count
            """,
            limit=limit,
        )
        return [
            {"file_path": record["file_path"], "entity_count": record["entity_count"]}
            for record in result
        ]


# ---------------------------------------------------------------------------
# Private helpers for query_entity_dependencies
# ---------------------------------------------------------------------------


def _validate_direction(direction: str) -> None:
    """Raise ValueError if direction is not one of the supported values."""
    allowed = {"upstream", "downstream", "both"}
    if direction not in allowed:
        raise ValueError(
            f"Invalid direction '{direction}'. Must be one of: {', '.join(sorted(allowed))}"
        )


def _downstream_cypher(depth: int) -> str:
    """Return Cypher for finding what the entity calls/imports (downstream)."""
    return f"""
    MATCH (entity)
    WHERE entity.name = $name OR entity.qualified_name = $name
    MATCH p = (entity)-[:CALLS|IMPORTS*1..{depth}]->(dep)
    WHERE dep <> entity
    WITH dep, relationships(p)[0] AS first_rel
    RETURN
        dep.qualified_name   AS qualified_name,
        dep.name             AS name,
        labels(dep)[0]       AS label,
        dep.file_path        AS file_path,
        type(first_rel)      AS relationship_type
    ORDER BY qualified_name
    """


def _upstream_cypher(depth: int) -> str:
    """Return Cypher for finding what calls/imports the entity (upstream)."""
    return f"""
    MATCH (entity)
    WHERE entity.name = $name OR entity.qualified_name = $name
    MATCH p = (caller)-[:CALLS|IMPORTS*1..{depth}]->(entity)
    WHERE caller <> entity
    WITH caller, relationships(p)[0] AS first_rel
    RETURN
        caller.qualified_name AS qualified_name,
        caller.name           AS name,
        labels(caller)[0]     AS label,
        caller.file_path      AS file_path,
        type(first_rel)       AS relationship_type
    ORDER BY qualified_name
    """


def _both_directions_cypher(depth: int) -> str:
    """Return Cypher for finding all nodes connected via CALLS/IMPORTS (both directions)."""
    return f"""
    MATCH (entity)
    WHERE entity.name = $name OR entity.qualified_name = $name
    MATCH p = (neighbor)-[:CALLS|IMPORTS*1..{depth}]-(entity)
    WHERE neighbor <> entity
    WITH neighbor, relationships(p)[0] AS first_rel
    RETURN
        neighbor.qualified_name AS qualified_name,
        neighbor.name           AS name,
        labels(neighbor)[0]     AS label,
        neighbor.file_path      AS file_path,
        type(first_rel)         AS relationship_type
    ORDER BY qualified_name
    """


def _row_to_node_info(record: Any) -> NodeInfo:
    """Convert a Neo4j record row to a NodeInfo dataclass."""
    return NodeInfo(
        qualified_name=record["qualified_name"] or "",
        name=record["name"] or "",
        label=record["label"] or "",
        file_path=record["file_path"] or "",
    )


def _row_to_node_info_with_rel(record: Any) -> NodeInfoWithRel:
    """Convert a Neo4j record row (with relationship_type) to a NodeInfoWithRel."""
    return NodeInfoWithRel(
        qualified_name=record["qualified_name"] or "",
        name=record["name"] or "",
        label=record["label"] or "",
        file_path=record["file_path"] or "",
        relationship_type=record["relationship_type"] or "",
    )


def trace_path_to_seed(
    driver: Driver,
    seed_ids: list[int],
    file_path: str,
    max_hops: int = 6,
) -> str:
    """Find the shortest path from any seed node to the given file in the graph.

    Returns a human-readable string like:
      "DateField -[CONTAINS]-> fields.py"
    or "(no path traced)" if unreachable within max_hops.
    If the file_path IS a seed (direct match), returns "direct seed".
    Returns "(trace error)" on any exception.
    """
    try:
        return _run_trace_query(driver, seed_ids, file_path, max_hops)
    except Exception as exc:
        logger.debug("trace_path_to_seed failed for '%s': %s", file_path, exc)
        return "(trace error)"


def trace_path_ids_to_seed(
    driver: Driver,
    seed_ids: list[int],
    file_path: str,
    max_hops: int = 6,
) -> list[str]:
    """Find the shortest path from any seed to the file and return node IDs (qualified names)."""
    with driver.session() as session:
        # We query for the shortest path and return the list of qualified_names
        result = session.run(
            f"""
            MATCH (seed) WHERE id(seed) IN $seed_ids
            MATCH (target:File {{file_path: $file_path}})
            MATCH p = shortestPath((seed)-[*..{max_hops}]-(target))
            RETURN [node IN nodes(p) | node.qualified_name] AS path_ids
            ORDER BY length(p) ASC
            LIMIT 1
            """,
            seed_ids=seed_ids,
            file_path=file_path,
        ).single()

    if not result or not result["path_ids"]:
        return []
    return result["path_ids"]


def _run_trace_query(
    driver: Driver,
    seed_ids: list[int],
    file_path: str,
    max_hops: int,
) -> str:
    """Execute the shortest-path Cypher and format the result."""
    # Check if the target file is itself a seed node
    with driver.session() as session:
        direct = session.run(
            "MATCH (f:File {file_path: $fp}) WHERE id(f) IN $ids RETURN count(f) AS cnt",
            fp=file_path,
            ids=seed_ids,
        ).single()
        if direct and direct["cnt"] > 0:
            return "direct seed"

        result = session.run(
            f"""
            MATCH (seed) WHERE id(seed) IN $seed_ids
            MATCH (target:File {{file_path: $file_path}})
            MATCH p = shortestPath((seed)-[*..{max_hops}]-(target))
            RETURN
                [node IN nodes(p) | coalesce(node.name, node.file_path, '')] AS node_names,
                [rel IN relationships(p) | type(rel)] AS rel_types,
                length(p) AS path_length
            ORDER BY path_length ASC
            LIMIT 1
            """,
            seed_ids=seed_ids,
            file_path=file_path,
        ).single()

    if not result:
        return "(no path traced)"

    return _format_path(result["node_names"], result["rel_types"])


def get_full_graph(driver: Driver) -> dict[str, list[dict]]:
    """Return every single node and edge in the database."""
    with driver.session() as session:
        # Fetch nodes
        nodes_res = session.run(
            """
            MATCH (n)
            RETURN n.qualified_name AS id,
                   n.name AS name,
                   labels(n)[0] AS label,
                   n.file_path AS file_path,
                   coalesce(n.line_number, 0) AS line_number,
                   coalesce(n.end_line, 0) AS line_end
            """
        )
        nodes = [dict(r) for r in nodes_res]

        # Fetch edges
        edges_res = session.run(
            """
            MATCH (a)-[r]->(b)
            RETURN a.qualified_name AS source,
                   b.qualified_name AS target,
                   type(r)          AS type
            """
        )
        edges = [dict(r) for r in edges_res]

    return {"nodes": nodes, "edges": edges}


def get_subgraph_for_nodes(
    driver: Driver,
    qualified_names: list[str],
) -> dict[str, list[dict]]:
    """Return all nodes and direct edges between the given qualified names.

    Ensures all requested nodes are included even if they are isolated.
    """
    if not qualified_names:
        return {"nodes": [], "edges": []}

    nodes: list[dict] = []
    edges: list[dict] = []

    with driver.session() as session:
        # 1. Fetch all nodes in the set
        node_result = session.run(
            """
            MATCH (n)
            WHERE n.qualified_name IN $ids
            RETURN n.qualified_name AS id,
                   n.name AS name,
                   labels(n)[0] AS label,
                   n.file_path AS file_path,
                   coalesce(n.line_number, 0) AS line_number,
                   coalesce(n.end_line, 0) AS line_end
            """,
            ids=qualified_names,
        )
        nodes = [dict(r) for r in node_result]

        # 2. Fetch edges only between these nodes
        edge_result = session.run(
            """
            MATCH (a)-[r]->(b)
            WHERE a.qualified_name IN $ids AND b.qualified_name IN $ids
            RETURN a.qualified_name AS source,
                   b.qualified_name AS target,
                   type(r)          AS type
            """,
            ids=qualified_names,
        )
        edges = [dict(r) for r in edge_result]

    return {"nodes": nodes, "edges": edges}


def get_subgraph_by_prefix(
    driver: Driver,
    prefix: str,
) -> dict[str, list[dict]]:
    """Return all nodes and edges where file_path starts with the given prefix.

    Useful for focusing the visualization on a specific directory or file.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a)-[r]-(b)
            WHERE a.file_path STARTS WITH $prefix AND b.file_path STARTS WITH $prefix
            RETURN
                a.qualified_name AS src_id,
                a.name           AS src_name,
                labels(a)[0]     AS src_label,
                a.file_path      AS src_file,
                type(r)          AS rel_type,
                b.qualified_name AS tgt_id,
                b.name           AS tgt_name,
                labels(b)[0]     AS tgt_label,
                b.file_path      AS tgt_file
            """,
            prefix=prefix,
        )
        rows = result.data()

    nodes_by_id: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[frozenset] = set()

    for row in rows:
        for p, qname in [("src", row["src_id"]), ("tgt", row["tgt_id"])]:
            if qname not in nodes_by_id:
                nodes_by_id[qname] = {
                    "id": qname,
                    "name": row[f"{p}_name"],
                    "label": row[f"{p}_label"] or "Unknown",
                    "file_path": row[f"{p}_file"] or "",
                }

        edge_key = frozenset({row["src_id"], row["tgt_id"], row["rel_type"]})
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append(
                {
                    "source": row["src_id"],
                    "target": row["tgt_id"],
                    "type": row["rel_type"],
                }
            )

    return {"nodes": list(nodes_by_id.values()), "edges": edges}


def get_node_detail(driver: Driver, qualified_name: str) -> dict[str, Any]:
    """Return full detail for a single node including its neighborhood."""
    with driver.session() as session:
        # Get core node attributes
        node_res = session.run(
            """
            MATCH (n {qualified_name: $qname})
            RETURN n.qualified_name AS id,
                   n.name AS name,
                   labels(n)[0] AS label,
                   n.file_path AS file_path,
                   coalesce(n.line_number, 0) AS line_number,
                   coalesce(n.end_line, 0) AS end_line
            """,
            qname=qualified_name,
        ).single()

        if not node_res:
            return {}

        node_data = dict(node_res)

        # Get incoming relationships
        incoming_res = session.run(
            """
            MATCH (other)-[r]->(n {qualified_name: $qname})
            RETURN other.qualified_name AS qualified_name,
                   other.name AS name,
                   labels(other)[0] AS label,
                   other.file_path AS file_path,
                   type(r) AS relationship
            """,
            qname=qualified_name,
        )
        incoming = [dict(r) for r in incoming_res]

        # Get outgoing relationships
        outgoing_res = session.run(
            """
            MATCH (n {qualified_name: $qname})-[r]->(other)
            RETURN other.qualified_name AS qualified_name,
                   other.name AS name,
                   labels(other)[0] AS label,
                   other.file_path AS file_path,
                   type(r) AS relationship
            """,
            qname=qualified_name,
        )
        outgoing = [dict(r) for r in outgoing_res]

    return {
        "node": node_data,
        "incoming": incoming,
        "outgoing": outgoing,
    }


def _format_path(node_names: list[str], rel_types: list[str]) -> str:
    """Interleave node names and relationship types into a readable path string."""
    _MAX_NODE_LEN = 30
    parts: list[str] = []
    for i, name in enumerate(node_names):
        truncated = name[:_MAX_NODE_LEN] if len(name) > _MAX_NODE_LEN else name
        parts.append(truncated)
        if i < len(rel_types):
            parts.append(f"-[{rel_types[i]}]->")
    return " ".join(parts)


def delete_file_entities(driver: Driver, file_path: str) -> int:
    """Delete all nodes whose file_path matches and their relationships.

    Returns the number of nodes deleted.
    """
    with driver.session() as session:
        result = session.run(
            "MATCH (n {file_path: $fp}) DETACH DELETE n RETURN count(n) AS deleted",
            fp=file_path,
        )
        record = result.single()
        return record["deleted"] if record else 0
