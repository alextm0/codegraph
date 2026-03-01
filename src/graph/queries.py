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
            MATCH (cls:Class {qualified_name: $qname})-[:INHERITS_FROM*1..]->(ancestor:Class)
            RETURN ancestor.qualified_name AS qualified_name,
                   ancestor.name AS name,
                   labels(ancestor)[0] AS label,
                   ancestor.file_path AS file_path
            ORDER BY qualified_name
            """,
            qname=class_qname,
        )
        return [_row_to_node_info(r) for r in result]


def _row_to_node_info(record: Any) -> NodeInfo:
    """Convert a Neo4j record row to a NodeInfo dataclass."""
    return NodeInfo(
        qualified_name=record["qualified_name"] or "",
        name=record["name"] or "",
        label=record["label"] or "",
        file_path=record["file_path"] or "",
    )
