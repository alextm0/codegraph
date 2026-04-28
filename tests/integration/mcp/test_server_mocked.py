import json
from unittest.mock import MagicMock, patch
import pytest

from codegraph.mcp.tools import query_dependencies_impl


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.driver = MagicMock()
    state.project_root = "/project"
    return state


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
        payload = json.loads(result)
        assert payload["result_count"] == 1
        deps = payload["results"]
        assert deps[0]["name"] == "f"
        assert deps[0]["relationship_type"] == "CALLS"
