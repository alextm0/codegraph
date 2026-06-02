"""Unit tests for visualizer graph filtering."""

from __future__ import annotations

from codegraph.visualizer.graph_filter import (
    filter_graph_for_visualizer,
    is_visualizer_excluded,
)


def test_is_visualizer_excluded_fixture_paths() -> None:
    assert is_visualizer_excluded("tests/fixtures/flask/src/flask/app.py") is True
    assert is_visualizer_excluded("src/codegraph/mcp/server.py") is False


def test_filter_graph_for_visualizer_removes_nodes_and_edges() -> None:
    graph = {
        "nodes": [
            {"id": "src/app.py", "file_path": "src/app.py"},
            {
                "id": "tests/fixtures/flask/app.py",
                "file_path": "tests/fixtures/flask/app.py",
            },
        ],
        "edges": [
            {"source": "src/app.py", "target": "tests/fixtures/flask/app.py", "type": "IMPORTS"},
            {"source": "src/app.py", "target": "src/app.py", "type": "CONTAINS"},
        ],
    }

    filtered = filter_graph_for_visualizer(graph)

    assert len(filtered["nodes"]) == 1
    assert filtered["nodes"][0]["id"] == "src/app.py"
    assert len(filtered["edges"]) == 1
    assert filtered["edges"][0]["type"] == "CONTAINS"
