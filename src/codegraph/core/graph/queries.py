"""Read-only Cypher query functions for the code graph."""

import logging
from dataclasses import dataclass
from typing import Any

from neo4j import Driver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeInfo:
    """Structured result for a single graph node."""

    qualified_name: str
    name: str
    label: str
    file_path: str


def count_nodes_by_label(driver: Driver) -> dict[str, int]:
    """Return a mapping of node label -> count."""
    with driver.session() as session:
        result = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY label"
        )
        return {record["label"]: record["cnt"] for record in result}


def count_edges_by_type(driver: Driver) -> dict[str, int]:
    """Return a mapping of relationship type -> count."""
    with driver.session() as session:
        result = session.run(
            "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt ORDER BY rel_type"
        )
        return {record["rel_type"]: record["cnt"] for record in result}


def get_neighbors(driver: Driver, qualified_name: str) -> list[NodeInfo]:
    """Return all nodes directly connected (in either direction) to the given node."""
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


def get_file_contents(driver: Driver, file_path: str) -> list[NodeInfo]:
    """Return all entities directly contained in a file."""
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


def find_callers(driver: Driver, qualified_name: str) -> list[NodeInfo]:
    """Return all nodes that call the given node."""
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


def find_callees(driver: Driver, qualified_name: str) -> list[NodeInfo]:
    """Return all nodes called by the given node."""
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


def find_node_by_name(driver: Driver, name: str) -> list[NodeInfo]:
    """Return all nodes whose name property matches exactly."""
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


def get_inheritance_chain(driver: Driver, class_qname: str) -> list[NodeInfo]:
    """Return the full inheritance chain (ancestors) of a class, ordered from immediate parent upward."""
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
    driver: Driver,
    entity_name: str,
    direction: str = "both",
    depth: int = 1,
) -> list[NodeInfo]:
    """Return dependency nodes for a code entity.

    Args:
        driver: Active Neo4j driver.
        entity_name: Exact name or qualified_name of the entity to look up.
        direction: One of "upstream" (callers), "downstream" (callees), or "both".
        depth: How many hops to follow. 1 = direct only, 2 = include indirect.

    Returns:
        Deduplicated list of NodeInfo for all found dependencies.
    """
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

    results: list[NodeInfo] = []
    with driver.session() as session:
        records = session.run(cypher, name=entity_name)
        for record in records:
            results.append(_row_to_node_info(record))

    logger.debug(
        "query_entity_dependencies: found %d nodes for '%s' (direction=%s, depth=%d)",
        len(results),
        entity_name,
        direction,
        depth,
    )
    return results


def get_most_connected_files(driver: Driver, limit: int = 10) -> list[dict]:
    """Return files ranked by number of directly contained entities.

    Useful for understanding which files are the most structurally
    important in the codebase.

    Returns:
        List of dicts with keys "file_path" and "entity_count",
        sorted descending by entity_count.
    """
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
    MATCH (entity)-[:CALLS|IMPORTS*1..{depth}]->(dep)
    WHERE dep <> entity
    RETURN DISTINCT
        dep.qualified_name AS qualified_name,
        dep.name           AS name,
        labels(dep)[0]     AS label,
        dep.file_path      AS file_path
    ORDER BY qualified_name
    """


def _upstream_cypher(depth: int) -> str:
    """Return Cypher for finding what calls/imports the entity (upstream)."""
    return f"""
    MATCH (entity)
    WHERE entity.name = $name OR entity.qualified_name = $name
    MATCH (caller)-[:CALLS|IMPORTS*1..{depth}]->(entity)
    WHERE caller <> entity
    RETURN DISTINCT
        caller.qualified_name AS qualified_name,
        caller.name           AS name,
        labels(caller)[0]     AS label,
        caller.file_path      AS file_path
    ORDER BY qualified_name
    """


def _both_directions_cypher(depth: int) -> str:
    """Return Cypher for finding all nodes connected via CALLS/IMPORTS (both directions)."""
    return f"""
    MATCH (entity)
    WHERE entity.name = $name OR entity.qualified_name = $name
    MATCH (neighbor)-[:CALLS|IMPORTS*1..{depth}]-(entity)
    WHERE neighbor <> entity
    RETURN DISTINCT
        neighbor.qualified_name AS qualified_name,
        neighbor.name           AS name,
        labels(neighbor)[0]     AS label,
        neighbor.file_path      AS file_path
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
