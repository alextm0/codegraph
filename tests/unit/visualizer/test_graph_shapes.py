"""Tests for graph shape helpers used by the visualizer."""

from codegraph.visualizer.graph_filter import filter_graph_for_visualizer


def test_filter_graph_for_visualizer_drops_fixture_paths():
    graph = {
        "nodes": [
            {"id": "src/main.py::main", "file_path": "src/main.py", "name": "main"},
            {"id": "tests/fixtures/x.py::f", "file_path": "tests/fixtures/x.py", "name": "f"},
        ],
        "edges": [
            {
                "source": "src/main.py::main",
                "target": "tests/fixtures/x.py::f",
                "type": "CALLS",
            },
        ],
    }
    filtered = filter_graph_for_visualizer(graph)
    assert len(filtered["nodes"]) == 1
    assert filtered["nodes"][0]["file_path"] == "src/main.py"
    assert filtered["edges"] == []
