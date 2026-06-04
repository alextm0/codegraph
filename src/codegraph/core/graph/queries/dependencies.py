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
    driver: Driver | None = None,
    pattern: str = "",
    limit: int = 100,
    label: str | None = None,
    project_scope: str | None = None,
) -> list[NodeInfo]:
    """Return nodes whose name or qualified_name contains pattern (case-insensitive)."""
    if driver is None:
        driver = get_database_manager().get_driver()
    if project_scope is not None:
        project_scope = project_scope.replace("\\", "/")
    limit = max(1, min(limit, 500))
    label_clause = ""
    if label:
        label_clause = f"AND '{label}' IN labels(n)"
    with driver.session() as session:
        result = session.run(
            f"""
            MATCH (n)
            WHERE (n:Function OR n:Method OR n:Class OR n:File)
              AND (
                toLower(coalesce(n.name, '')) CONTAINS toLower($pattern)
                OR toLower(coalesce(n.qualified_name, '')) CONTAINS toLower($pattern)
                OR toLower(coalesce(n.file_path, '')) CONTAINS toLower($pattern)
              )
              AND ($scope IS NULL OR n.file_path STARTS WITH $scope)
              {label_clause}
            RETURN n.qualified_name AS qualified_name,
                   n.name AS name,
                   labels(n)[0] AS label,
                   n.file_path AS file_path
            ORDER BY qualified_name
            LIMIT $limit
            """,
            pattern=pattern,
            scope=project_scope,
            limit=limit,
        )
        return [_row_to_node_info(r) for r in result]


def search_symbols(
    driver: Driver | None = None,
    pattern: str = "",
    limit: int = 100,
    label: str | None = None,
    project_scope: str | None = None,
) -> list[NodeInfo]:
    """Search indexed symbols and files by substring (alias for find_node_by_pattern)."""
    return find_node_by_pattern(
        driver, pattern, limit=limit, label=label, project_scope=project_scope
    )


def get_inheritance_chain(
    driver: Driver | None = None, class_qname: str = ""
) -> list[NodeInfo]:
    """Return ancestors of a class by qualified_name, immediate parent first."""
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


def _resolve_class_nodes(
    driver: Driver, class_name: str, project_scope: str | None = None
) -> list[NodeInfo]:
    """Resolve Class nodes by short name or qualified_name."""
    if project_scope is not None:
        project_scope = project_scope.replace("\\", "/")
    with driver.session() as session:
        result = session.run(
            """
            MATCH (cls:Class)
            WHERE cls.name = $name OR cls.qualified_name = $name
              AND ($scope IS NULL OR cls.file_path STARTS WITH $scope)
            RETURN cls.qualified_name AS qualified_name,
                   cls.name AS name,
                   labels(cls)[0] AS label,
                   cls.file_path AS file_path
            ORDER BY qualified_name
            """,
            name=class_name,
            scope=project_scope,
        )
        return [_row_to_node_info(r) for r in result]


def query_class_hierarchy(
    driver: Driver | None = None,
    class_name: str = "",
    direction: str = "both",
    project_scope: str | None = None,
) -> list[NodeInfoWithRel]:
    """Return inheritance-related classes for a class name or qualified_name.

    Args:
        class_name: Short class name or qualified_name.
        direction: ``upstream`` (ancestors), ``downstream`` (subclasses), or ``both``.
    """
    if driver is None:
        driver = get_database_manager().get_driver()
    _validate_direction(direction)
    if project_scope is not None:
        project_scope = project_scope.replace("\\", "/")

    roots = _resolve_class_nodes(driver, class_name, project_scope)
    if not roots:
        return []

    results: list[NodeInfoWithRel] = []
    seen: set[str] = set()

    def _add(node: NodeInfo, rel: str) -> None:
        if node.qualified_name in seen:
            return
        seen.add(node.qualified_name)
        results.append(
            NodeInfoWithRel(
                qualified_name=node.qualified_name,
                name=node.name,
                label=node.label,
                file_path=node.file_path,
                relationship_type=rel,
            )
        )

    with driver.session() as session:
        for root in roots:
            if direction in ("upstream", "both"):
                records = session.run(
                    """
                    MATCH p = (cls:Class {qualified_name: $qname})
                              -[:INHERITS_FROM*1..]->(ancestor:Class)
                    RETURN ancestor.qualified_name AS qualified_name,
                           ancestor.name AS name,
                           labels(ancestor)[0] AS label,
                           ancestor.file_path AS file_path
                    ORDER BY length(p) ASC
                    """,
                    qname=root.qualified_name,
                )
                for record in records:
                    _add(_row_to_node_info(record), "INHERITS_FROM")

            if direction in ("downstream", "both"):
                records = session.run(
                    """
                    MATCH p = (descendant:Class)-[:INHERITS_FROM*1..]->
                              (cls:Class {qualified_name: $qname})
                    RETURN descendant.qualified_name AS qualified_name,
                           descendant.name AS name,
                           labels(descendant)[0] AS label,
                           descendant.file_path AS file_path
                    ORDER BY length(p) ASC
                    """,
                    qname=root.qualified_name,
                )
                for record in records:
                    _add(_row_to_node_info(record), "INHERITS_FROM")

    return results


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
