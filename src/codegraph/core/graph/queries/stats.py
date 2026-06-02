"""Graph statistics and dead-code analysis queries."""

from neo4j import Driver

from codegraph.core.graph.database import get_database_manager
from codegraph.core.graph.queries.models import DeadCodeNode


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
