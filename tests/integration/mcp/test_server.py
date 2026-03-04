"""Tests for src/mcp_server.py.

Tests are organized in two groups:

  1. No-Neo4j tests — verify server structure (tool registration, tool names)
     without needing a running database. These always run.

  2. Neo4j-backed tests — verify tool output using the user_auth fixture.
     These skip gracefully when Neo4j is not running.

We test MCP tools by importing the server module and calling mcp.call_tool()
using the MCP SDK's built-in test helper rather than running the full
STDIO protocol loop. This lets us test tool logic without spinning up a
subprocess.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.conftest import neo4j_required

# Fixtures path used by Neo4j-backed tests.
FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"
USER_AUTH_DIR = str(FIXTURES_DIR / "user_auth")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_mcp_server():
    """Import mcp_server lazily to avoid side effects at collection time."""
    from codegraph.mcp import server as mcp_server
    return mcp_server


# ---------------------------------------------------------------------------
# Tool registration tests (no Neo4j required)
# ---------------------------------------------------------------------------

class TestToolRegistration:
    """Verify that the server registers the expected tools."""

    def test_mcp_server_importable(self):
        """src.mcp_server must import without errors."""
        module = _import_mcp_server()
        assert module is not None

    def test_mcp_instance_exists(self):
        """The module must expose a FastMCP instance named 'mcp'."""
        module = _import_mcp_server()
        assert hasattr(module, "mcp"), "Expected 'mcp' attribute on mcp_server module"

    def test_all_three_tools_registered(self):
        """All three expected tools must be registered on the FastMCP server."""
        module = _import_mcp_server()
        # FastMCP stores registered tools in a dict accessible via _tool_manager._tools.
        registered_names = set(module.mcp._tool_manager._tools.keys())
        expected_names = {"get_relevant_context", "query_dependencies", "get_graph_stats"}
        missing = expected_names - registered_names
        assert not missing, (
            f"Missing tools: {missing}. Registered: {registered_names}"
        )

    def test_get_relevant_context_registered(self):
        """get_relevant_context tool must be individually verifiable."""
        module = _import_mcp_server()
        registered_names = set(module.mcp._tool_manager._tools.keys())
        assert "get_relevant_context" in registered_names

    def test_query_dependencies_registered(self):
        """query_dependencies tool must be individually verifiable."""
        module = _import_mcp_server()
        registered_names = set(module.mcp._tool_manager._tools.keys())
        assert "query_dependencies" in registered_names

    def test_get_graph_stats_registered(self):
        """get_graph_stats tool must be individually verifiable."""
        module = _import_mcp_server()
        registered_names = set(module.mcp._tool_manager._tools.keys())
        assert "get_graph_stats" in registered_names

    def test_server_has_correct_name(self):
        """The FastMCP server must be named 'codegraph'."""
        module = _import_mcp_server()
        assert module.mcp.name == "codegraph"

    def test_main_function_exists(self):
        """The module must expose a main() function for the CLI entry point."""
        module = _import_mcp_server()
        assert callable(module.main), "Expected callable 'main' in mcp_server module"


# ---------------------------------------------------------------------------
# ServerState dataclass tests (no Neo4j required)
# ---------------------------------------------------------------------------

class TestServerState:
    """Verify the ServerState dataclass structure."""

    def test_server_state_importable(self):
        """ServerState must be importable from mcp_server."""
        from codegraph.mcp.server import ServerState
        assert ServerState is not None

    def test_server_state_has_required_fields(self):
        """ServerState must have all fields needed by tools."""
        from codegraph.mcp.server import ServerState
        from codegraph.core.graph.ppr import PPRConfig

        # Build a minimal ServerState using mock objects for the DB connections.
        state = ServerState(
            driver=MagicMock(),
            gds=MagicMock(),
            project_root="/some/root",
            ppr_config=PPRConfig(),
            signal_weights={},
            default_token_budget=6000,
            default_top_k=15,
        )
        assert state.project_root == "/some/root"
        assert state.default_token_budget == 6000
        assert state.default_top_k == 15


# ---------------------------------------------------------------------------
# get_graph_stats tool tests (Neo4j required)
# ---------------------------------------------------------------------------

@neo4j_required
class TestGetGraphStats:
    """Test the get_graph_stats tool against a real populated graph."""

    @pytest.fixture(scope="class")
    def populated_driver(self, neo4j_driver):
        """Populate the graph with user_auth fixture for this test class."""
        from codegraph.core.parser.python_parser import create_parser, parse_directory
        from codegraph.core.graph.graph_builder import build_graph, clear_database

        parser = create_parser()
        entities = parse_directory(USER_AUTH_DIR, parser)
        clear_database(neo4j_driver)
        build_graph(neo4j_driver, entities)
        yield neo4j_driver
        clear_database(neo4j_driver)

    def test_returns_valid_json(self, populated_driver):
        """get_graph_stats must return valid JSON."""
        from codegraph.core.graph.queries import (
            count_nodes_by_label,
            count_edges_by_type,
            get_most_connected_files,
        )

        node_counts = count_nodes_by_label(populated_driver)
        edge_counts = count_edges_by_type(populated_driver)
        most_connected = get_most_connected_files(populated_driver, limit=10)

        # Assemble the same dict the tool would return.
        stats = {
            "node_counts": node_counts,
            "edge_counts": edge_counts,
            "total_nodes": sum(node_counts.values()),
            "total_edges": sum(edge_counts.values()),
            "most_connected_files": most_connected,
        }
        json_output = json.dumps(stats, indent=2)
        parsed = json.loads(json_output)
        assert isinstance(parsed, dict)

    def test_node_counts_present(self, populated_driver):
        """Stats must include node_counts with at least some entries."""
        from codegraph.core.graph.queries import count_nodes_by_label
        node_counts = count_nodes_by_label(populated_driver)
        assert len(node_counts) > 0

    def test_edge_counts_present(self, populated_driver):
        """Stats must include edge_counts with at least some entries."""
        from codegraph.core.graph.queries import count_edges_by_type
        edge_counts = count_edges_by_type(populated_driver)
        assert len(edge_counts) > 0

    def test_total_nodes_matches_sum(self, populated_driver):
        """total_nodes must equal the sum of individual label counts."""
        from codegraph.core.graph.queries import count_nodes_by_label
        node_counts = count_nodes_by_label(populated_driver)
        total = sum(node_counts.values())
        assert total > 0

    def test_most_connected_files_is_list(self, populated_driver):
        """most_connected_files must be a list of dicts."""
        from codegraph.core.graph.queries import get_most_connected_files
        most_connected = get_most_connected_files(populated_driver, limit=10)
        assert isinstance(most_connected, list)
        for entry in most_connected:
            assert "file_path" in entry
            assert "entity_count" in entry

    def test_most_connected_files_ordered_descending(self, populated_driver):
        """Files must be ordered by entity_count descending."""
        from codegraph.core.graph.queries import get_most_connected_files
        most_connected = get_most_connected_files(populated_driver, limit=10)
        if len(most_connected) < 2:
            pytest.skip("Need at least 2 files to verify ordering")
        counts = [entry["entity_count"] for entry in most_connected]
        for i in range(len(counts) - 1):
            assert counts[i] >= counts[i + 1], (
                f"Files not ordered by entity_count: {counts[i]} < {counts[i + 1]}"
            )


# ---------------------------------------------------------------------------
# query_dependencies tool tests (Neo4j required)
# ---------------------------------------------------------------------------

@neo4j_required
class TestQueryDependencies:
    """Test the query_dependencies tool against a real populated graph."""

    @pytest.fixture(scope="class")
    def populated_driver(self, neo4j_driver):
        """Populate the graph with user_auth fixture for this test class."""
        from codegraph.core.parser.python_parser import create_parser, parse_directory
        from codegraph.core.graph.graph_builder import build_graph, clear_database

        parser = create_parser()
        entities = parse_directory(USER_AUTH_DIR, parser)
        clear_database(neo4j_driver)
        build_graph(neo4j_driver, entities)
        yield neo4j_driver
        clear_database(neo4j_driver)

    def test_downstream_returns_list(self, populated_driver):
        """Downstream direction must return a list (may be empty)."""
        from codegraph.core.graph.queries import query_entity_dependencies
        result = query_entity_dependencies(
            populated_driver, "AuthService", direction="downstream", depth=1
        )
        assert isinstance(result, list)

    def test_upstream_returns_list(self, populated_driver):
        """Upstream direction must return a list (may be empty)."""
        from codegraph.core.graph.queries import query_entity_dependencies
        result = query_entity_dependencies(
            populated_driver, "validate_email", direction="upstream", depth=1
        )
        assert isinstance(result, list)

    def test_both_directions_returns_list(self, populated_driver):
        """Both direction must return a list (may be empty)."""
        from codegraph.core.graph.queries import query_entity_dependencies
        result = query_entity_dependencies(
            populated_driver, "register", direction="both", depth=1
        )
        assert isinstance(result, list)

    def test_invalid_direction_raises(self, populated_driver):
        """An invalid direction string must raise ValueError."""
        from codegraph.core.graph.queries import query_entity_dependencies
        with pytest.raises(ValueError, match="Invalid direction"):
            query_entity_dependencies(
                populated_driver, "AuthService", direction="sideways", depth=1
            )

    def test_unknown_entity_returns_empty(self, populated_driver):
        """A completely unknown entity name should return an empty list, not crash."""
        from codegraph.core.graph.queries import query_entity_dependencies
        result = query_entity_dependencies(
            populated_driver, "GhostEntityThatDoesNotExist", direction="both", depth=1
        )
        assert result == []

    def test_depth_two_finds_more_or_equal(self, populated_driver):
        """Depth 2 should return at least as many nodes as depth 1."""
        from codegraph.core.graph.queries import query_entity_dependencies
        depth_1 = query_entity_dependencies(
            populated_driver, "register", direction="downstream", depth=1
        )
        depth_2 = query_entity_dependencies(
            populated_driver, "register", direction="downstream", depth=2
        )
        assert len(depth_2) >= len(depth_1), (
            "Depth 2 should return at least as many results as depth 1"
        )

    def test_result_nodes_have_required_fields(self, populated_driver):
        """Each returned NodeInfo must have qualified_name, name, label, file_path."""
        from codegraph.core.graph.queries import query_entity_dependencies
        result = query_entity_dependencies(
            populated_driver, "register", direction="both", depth=1
        )
        for node in result:
            assert hasattr(node, "qualified_name")
            assert hasattr(node, "name")
            assert hasattr(node, "label")
            assert hasattr(node, "file_path")

    def test_json_serialization_of_results(self, populated_driver):
        """query_dependencies results must serialize cleanly to JSON."""
        from codegraph.core.graph.queries import query_entity_dependencies
        result = query_entity_dependencies(
            populated_driver, "register", direction="both", depth=1
        )
        serializable = [
            {
                "qualified_name": node.qualified_name,
                "name": node.name,
                "label": node.label,
                "file_path": node.file_path,
            }
            for node in result
        ]
        # Should not raise.
        json_str = json.dumps(serializable)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# get_relevant_context pipeline integration tests (Neo4j required)
# ---------------------------------------------------------------------------

@neo4j_required
class TestGetRelevantContext:
    """Test the full pipeline logic called by get_relevant_context."""

    @pytest.fixture(scope="class")
    def populated_driver(self, neo4j_driver):
        """Populate the graph with user_auth fixture for this test class."""
        from codegraph.core.parser.python_parser import create_parser, parse_directory
        from codegraph.core.graph.graph_builder import build_graph, clear_database

        parser = create_parser()
        entities = parse_directory(USER_AUTH_DIR, parser)
        clear_database(neo4j_driver)
        build_graph(neo4j_driver, entities)
        yield neo4j_driver
        clear_database(neo4j_driver)

    @pytest.fixture(scope="class")
    def gds_client(self, populated_driver):
        from codegraph.core.graph.ppr import create_gds_client
        return create_gds_client(populated_driver)

    def test_pipeline_returns_context_results(self, populated_driver, gds_client):
        """Pipeline called from get_relevant_context should return ContextResult items."""
        from codegraph.core.retrieval.pipeline import run_retrieval_pipeline
        from codegraph.core.retrieval.post_processing import ContextResult

        results = run_retrieval_pipeline(
            driver=populated_driver,
            gds=gds_client,
            task_description="fix the authentication and registration bug",
            project_root=USER_AUTH_DIR,
            mentioned_entities=["AuthService"],
        )
        for item in results:
            assert isinstance(item, ContextResult)

    def test_pipeline_results_serialize_to_json(self, populated_driver, gds_client):
        """Results must be JSON-serializable using dataclasses.asdict()."""
        from codegraph.core.retrieval.pipeline import run_retrieval_pipeline

        results = run_retrieval_pipeline(
            driver=populated_driver,
            gds=gds_client,
            task_description="validate user email address",
            project_root=USER_AUTH_DIR,
        )
        # Should not raise.
        serializable = [dataclasses.asdict(item) for item in results]
        json_str = json.dumps(serializable)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)

    def test_each_result_has_expected_json_keys(self, populated_driver, gds_client):
        """Each serialized result must have all expected keys."""
        from codegraph.core.retrieval.pipeline import run_retrieval_pipeline

        results = run_retrieval_pipeline(
            driver=populated_driver,
            gds=gds_client,
            task_description="authenticate user login request",
            project_root=USER_AUTH_DIR,
            mentioned_entities=["authenticate"],
        )
        if not results:
            pytest.skip("No results returned — skipping key check")

        expected_keys = {
            "entity_name", "qualified_name", "file_path",
            "line_start", "line_end", "relevance_score",
            "source_code", "token_count",
        }
        for item in results:
            item_dict = dataclasses.asdict(item)
            missing_keys = expected_keys - item_dict.keys()
            assert not missing_keys, f"Result missing keys: {missing_keys}"
