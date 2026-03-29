import json
from unittest.mock import MagicMock, patch
import pytest

from codegraph.mcp.tools import (
    get_graph_stats_impl,
    query_dependencies_impl,
    find_dead_code_impl,
)


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.driver = MagicMock()
    state.project_root = "/project"
    return state


def test_get_graph_stats_mocked(mock_state):
    """Verify get_graph_stats_impl with a mocked state."""
    with patch("codegraph.mcp.tools.count_nodes_by_label") as mock_nodes:
        mock_nodes.return_value = {"File": 10, "Function": 50}
        with patch("codegraph.mcp.tools.count_edges_by_type") as mock_edges:
            mock_edges.return_value = {"CONTAINS": 50, "CALLS": 100}
            with patch("codegraph.mcp.tools.get_most_connected_files") as mock_files:
                mock_files.return_value = [{"file_path": "/project/a.py", "entity_count": 5}]

                result = get_graph_stats_impl(mock_state)

                assert result is not None
                stats = json.loads(result)
                assert stats["total_nodes"] == 60
                assert stats["total_edges"] == 150
                assert stats["node_counts"]["File"] == 10
                # most_connected_files now uses relative paths
                assert stats["most_connected_files"][0]["file_path"] == "a.py"


def test_query_dependencies_mocked(mock_state):
    """Verify query_dependencies_impl with a mocked state — includes relationship_type."""
    from codegraph.core.graph.queries import NodeInfoWithRel

    mock_node = NodeInfoWithRel(
        qualified_name="a::f",
        name="f",
        label="Function",
        file_path="a.py",
        relationship_type="CALLS",
    )

    with patch("codegraph.mcp.tools.query_entity_dependencies") as mock_deps:
        mock_deps.return_value = [mock_node]

        result = query_dependencies_impl("f", "both", 1, mock_state)

        assert result is not None
        deps = json.loads(result)
        assert len(deps) == 1
        assert deps[0]["name"] == "f"
        assert deps[0]["relationship_type"] == "CALLS"


def test_find_dead_code_mocked(mock_state):
    """Verify find_dead_code_impl groups results by file and includes line numbers."""
    from codegraph.core.graph.queries import DeadCodeNode

    mock_node = DeadCodeNode(
        qualified_name="a.py::dead",
        name="dead",
        label="Function",
        file_path="/project/a.py",
        line_number=42,
    )

    with patch("codegraph.mcp.tools.find_dead_code") as mock_dead:
        mock_dead.return_value = [mock_node]

        result = find_dead_code_impl(10, mock_state)

        assert result is not None
        output = json.loads(result)
        assert output["total_count"] == 1
        assert "a.py" in output["by_file"]
        entry = output["by_file"]["a.py"][0]
        assert entry["name"] == "dead"
        assert entry["line"] == 42
        assert entry["type"] == "function"
