"""Tests for src/mcp_server.py.

Tests are organized in three groups:

  1. No-Neo4j tests — verify server structure (tool registration, tool names)
     without needing a running database. These always run.

  2. Mocked-state tool tests — verify the full JSON contract of both MCP tools
     via get_relevant_context_impl and query_dependencies_impl with mocked state.
     These always run (no Neo4j needed).

  3. Neo4j-backed tests — verify tool output using the user_auth fixture.
     These skip gracefully when Neo4j is not running.

We test MCP tools by importing the server module and calling mcp.call_tool()
using the MCP SDK's built-in test helper rather than running the full
STDIO protocol loop. This lets us test tool logic without spinning up a
subprocess.
"""

import dataclasses
import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_exactly_two_tools_registered(self):
        """Exactly 2 tools must be registered: get_relevant_context and query_dependencies."""
        module = _import_mcp_server()
        registered_names = set(module.mcp._tool_manager._tools.keys())
        expected_names = {"get_relevant_context", "query_dependencies"}
        assert registered_names == expected_names, (
            f"Expected exactly {expected_names}, got: {registered_names}"
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
            config_path="/some/root/config.yaml",
            indexing_lock=threading.Lock(),
            indexing_in_progress=False,
        )
        assert state.project_root == "/some/root"
        assert state.default_token_budget == 6000
        assert state.default_top_k == 15


# ---------------------------------------------------------------------------
# MCP tool contract tests with mocked state (no Neo4j required)
# ---------------------------------------------------------------------------

def _make_mock_state(project_root="/project", default_top_k=15, default_token_budget=6000):
    """Build a minimal ServerState mock for tool testing."""
    from codegraph.core.graph.ppr import PPRConfig
    from codegraph.mcp.server import ServerState

    return ServerState(
        driver=MagicMock(),
        gds=MagicMock(),
        project_root=project_root,
        ppr_config=PPRConfig(),
        signal_weights={},
        default_token_budget=default_token_budget,
        default_top_k=default_top_k,
        config_path="/project/config.yaml",
        indexing_lock=threading.Lock(),
        indexing_in_progress=False,
    )


class TestMCPToolsWithMockedState:
    """Verify the JSON contract of both MCP tools using mocked ServerState.

    These tests exercise the full tool implementation path without Neo4j.
    """

    def test_get_relevant_context_returns_summary_and_results(self):
        """get_relevant_context_impl must return JSON with summary + results."""
        from codegraph.mcp.tools import get_relevant_context_impl
        from codegraph.core.retrieval.post_processing import ContextResult

        state = _make_mock_state()
        result = ContextResult(
            entity_name="login",
            entity_type="Function",
            qualified_name="/project/auth.py::login",
            file_path="/project/auth.py",
            line_start=1,
            line_end=10,
            relevance_score=0.95,
            source_code="def login(): pass",
            token_count=50,
        )

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_retrieval_pipeline", return_value=[result]),
        ):
            output = get_relevant_context_impl("fix auth", None, None, 0, 0, state)

        payload = json.loads(output)
        assert payload["summary"]["result_count"] == 1
        assert len(payload["results"]) == 1
        assert payload["results"][0]["entity_name"] == "login"

    def test_get_relevant_context_empty_graph_returns_error(self):
        """get_relevant_context_impl on empty graph must return error JSON."""
        from codegraph.mcp.tools import get_relevant_context_impl

        state = _make_mock_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=True),
            patch("codegraph.mcp.tools._start_background_index"),
        ):
            output = get_relevant_context_impl("task", None, None, 0, 0, state)

        payload = json.loads(output)
        assert "error" in payload

    def test_get_relevant_context_no_results_returns_hint(self):
        """get_relevant_context_impl with zero results must include a hint."""
        from codegraph.mcp.tools import get_relevant_context_impl

        state = _make_mock_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_retrieval_pipeline", return_value=[]),
        ):
            output = get_relevant_context_impl("task", None, None, 0, 0, state)

        payload = json.loads(output)
        assert payload["results"] == []
        assert "hint" in payload

    def test_get_relevant_context_result_fields(self):
        """Each result entry must contain all required fields."""
        from codegraph.mcp.tools import get_relevant_context_impl
        from codegraph.core.retrieval.post_processing import ContextResult

        state = _make_mock_state()
        result = ContextResult(
            entity_name="register",
            entity_type="Method",
            qualified_name="/project/auth.py::AuthService.register",
            file_path="/project/auth.py",
            line_start=20,
            line_end=35,
            relevance_score=0.8,
            source_code="def register(self): ...",
            token_count=120,
        )

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_retrieval_pipeline", return_value=[result]),
        ):
            output = get_relevant_context_impl("register user", None, None, 0, 0, state)

        item = json.loads(output)["results"][0]
        required_fields = {"entity_name", "entity_type", "qualified_name", "file_path", "lines", "relevance_score", "token_count", "source_code"}
        missing = required_fields - item.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_query_dependencies_returns_result_count_and_results(self):
        """query_dependencies_impl must return result_count + results list."""
        from codegraph.mcp.tools import query_dependencies_impl
        from codegraph.core.graph.queries import NodeInfoWithRel

        state = _make_mock_state()
        node = NodeInfoWithRel(
            qualified_name="/project/auth.py::validate",
            name="validate",
            label="Function",
            file_path="/project/auth.py",
            relationship_type="CALLS",
        )

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.query_entity_dependencies", return_value=[node]),
        ):
            output = query_dependencies_impl("login", "downstream", 1, state)

        payload = json.loads(output)
        assert payload["result_count"] == 1
        assert payload["results"][0]["relationship_type"] == "CALLS"

    def test_query_dependencies_invalid_direction_returns_error(self):
        """query_dependencies_impl with invalid direction must return error JSON."""
        from codegraph.mcp.tools import query_dependencies_impl

        state = _make_mock_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.query_entity_dependencies", side_effect=ValueError("Invalid direction")),
        ):
            output = query_dependencies_impl("login", "sideways", 1, state)

        payload = json.loads(output)
        assert "error" in payload

    def test_query_dependencies_unknown_entity_returns_hint(self):
        """query_dependencies_impl with no results must include a hint."""
        from codegraph.mcp.tools import query_dependencies_impl

        state = _make_mock_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.query_entity_dependencies", return_value=[]),
        ):
            output = query_dependencies_impl("GhostEntity", "both", 1, state)

        payload = json.loads(output)
        assert payload["result_count"] == 0
        assert "hint" in payload

    def test_query_dependencies_result_paths_are_relative(self):
        """query_dependencies_impl must return relative file paths."""
        from codegraph.mcp.tools import query_dependencies_impl
        from codegraph.core.graph.queries import NodeInfoWithRel

        state = _make_mock_state(project_root="/project")
        node = NodeInfoWithRel(
            qualified_name="/project/src/auth.py::login",
            name="login",
            label="Function",
            file_path="/project/src/auth.py",
            relationship_type="IMPORTS",
        )

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.query_entity_dependencies", return_value=[node]),
        ):
            output = query_dependencies_impl("login", "upstream", 1, state)

        payload = json.loads(output)
        fp = payload["results"][0]["file_path"]
        assert not fp.startswith("/project"), f"Expected relative path, got: {fp}"


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
