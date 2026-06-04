"""Full-graph, subgraph, node detail, and file mutation queries."""

from typing import Any

from neo4j import Driver

from codegraph.core.graph.database import get_database_manager
from codegraph.core.graph.queries.dependencies import _row_to_node_info
from codegraph.core.graph.queries.models import NodeInfo
from codegraph.core.graph.utils import normalize_path


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


def get_full_graph(driver: Driver) -> dict[str, list[dict]]:
    """Return every single node and edge in the database."""
    with driver.session() as session:
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


def expand_qnames_with_file_nodes(
    qualified_names: list[str],
    *,
    file_paths: list[str] | None = None,
) -> list[str]:
    """Add File node ids for entity paths so CONTAINS edges appear in query subgraphs."""
    seen: dict[str, None] = dict.fromkeys(qualified_names)
    for qname in qualified_names:
        if "::" in qname:
            seen[normalize_path(qname.split("::", 1)[0])] = None
    for path in file_paths or ():
        if path:
            seen[normalize_path(path)] = None
    return list(seen)


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
