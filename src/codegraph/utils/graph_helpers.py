"""Shared Neo4j query helpers used by CLI and visualizer."""

from pathlib import Path

from neo4j import Driver


def fetch_seed_names(driver: Driver, seed_ids: list[int]) -> dict[int, str]:
    """Return {node_id: display_name} for a list of seed node IDs."""
    names: dict[int, str] = {}
    with driver.session() as session:
        result = session.run(
            "MATCH (n) WHERE id(n) IN $ids RETURN id(n) AS nid, "
            "coalesce(n.name, n.file_path, '') AS name",
            ids=seed_ids,
        )
        for r in result:
            names[r["nid"]] = r["name"] or ""
    return names


def verify_graph_project_root(
    driver: Driver, project_root: str | Path
) -> tuple[bool, str]:
    """Return whether a sample indexed file path exists under project_root."""
    root = Path(project_root)
    with driver.session() as session:
        record = session.run(
            "MATCH (f:File) WHERE f.file_path IS NOT NULL "
            "RETURN f.file_path AS fp LIMIT 1"
        ).single()
    if record is None:
        return True, "Graph is empty"
    sample_path = record["fp"]
    if (root / sample_path).exists():
        return True, sample_path
    return False, sample_path
