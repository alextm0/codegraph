"""Filter fixture and other clutter paths from visualizer graph payloads."""

from __future__ import annotations

from typing import Any

from codegraph.utils.ignore import is_ignored

# Paths hidden from the visualizer project tree and graph (not core app source).
VISUALIZER_EXCLUDE_PATTERNS: tuple[str, ...] = (
    ".codegraph_cache/",
    "tests/fixtures/",
    ".gemini/",
    ".agents/",
    ".claude/",
    "thesis/",
    "projects/",
    "site/",
    "frontend/node_modules/",
    ".worktrees/",
)


def config_exclude_patterns(raw_config: dict[str, Any] | None) -> list[str]:
    """Collect exclude patterns from config.yaml (parser + top-level)."""
    if not raw_config:
        return []
    patterns: list[str] = []
    patterns.extend(raw_config.get("parser", {}).get("exclude_patterns") or [])
    patterns.extend(raw_config.get("exclude_patterns") or [])
    return patterns


def visualizer_exclude_patterns(
    config_patterns: list[str] | None = None,
) -> list[str]:
    """Return merged visualizer + config exclude patterns."""
    merged = list(VISUALIZER_EXCLUDE_PATTERNS)
    for pattern in config_patterns or []:
        if pattern not in merged:
            merged.append(pattern)
    return merged


def is_visualizer_excluded(
    path: str | None,
    config_patterns: list[str] | None = None,
) -> bool:
    """Return True when a path should be hidden from the visualizer."""
    if not path:
        return False
    return is_ignored(path, visualizer_exclude_patterns(config_patterns))


def filter_graph_for_visualizer(
    graph: dict[str, list[dict[str, Any]]],
    config_patterns: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Drop nodes under excluded paths and edges whose endpoints were removed."""
    nodes = [
        node
        for node in graph.get("nodes", [])
        if not is_visualizer_excluded(
            node.get("file_path") or node.get("id"),
            config_patterns,
        )
    ]
    visible_ids = {node["id"] for node in nodes if node.get("id")}
    edges = [
        edge
        for edge in graph.get("edges", [])
        if edge.get("source") in visible_ids and edge.get("target") in visible_ids
    ]
    return {"nodes": nodes, "edges": edges}
