"""Filter fixture and other clutter paths from visualizer graph payloads."""

from __future__ import annotations

from typing import Any

from codegraph.utils.ignore import is_ignored

# Test fixture trees add large duplicate subgraphs (flask, user_auth) without
# helping exploration of the indexed project.
VISUALIZER_EXCLUDE_PATTERNS: tuple[str, ...] = ("tests/fixtures/",)


def is_visualizer_excluded(path: str | None) -> bool:
    """Return True when a path should be hidden from the visualizer."""
    if not path:
        return False
    return is_ignored(path, list(VISUALIZER_EXCLUDE_PATTERNS))


def filter_graph_for_visualizer(
    graph: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Drop nodes under excluded paths and edges whose endpoints were removed."""
    nodes = [
        node
        for node in graph.get("nodes", [])
        if not is_visualizer_excluded(node.get("file_path") or node.get("id"))
    ]
    visible_ids = {node["id"] for node in nodes if node.get("id")}
    edges = [
        edge
        for edge in graph.get("edges", [])
        if edge.get("source") in visible_ids and edge.get("target") in visible_ids
    ]
    return {"nodes": nodes, "edges": edges}
