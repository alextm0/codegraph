"""Entity dependency, caller/callee, and lookup queries."""

import logging
from typing import Any

from neo4j import Driver

from codegraph.core.graph.database import get_database_manager
from codegraph.core.graph.queries.models import NodeInfo, NodeInfoWithRel

logger = logging.getLogger(__name__)


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
