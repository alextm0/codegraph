"""Unit tests for mcp/tools.py — all Neo4j interactions are mocked."""

import json
import threading
from unittest.mock import MagicMock, patch

from codegraph.mcp.tools import (
    _graph_is_empty,
    _start_background_index,
    get_relevant_context_impl,
    query_dependencies_impl,
)
from codegraph.core.retrieval.pipeline import RawRetrievalResult
from codegraph.core.retrieval.post_processing import ContextResult
from codegraph.core.retrieval.seed_selection import PersonalizationVector


def _make_state(
    project_root="/project",
    default_top_k=30,
    default_token_budget=6000,
    indexing_in_progress=False,
    exclude_seed_paths=None,
):
    state = MagicMock()
    state.driver = MagicMock()
    state.gds = MagicMock()
    state.project_root = project_root
    state.default_top_k = default_top_k
    state.default_token_budget = default_token_budget
    state.indexing_in_progress = indexing_in_progress
    state.indexing_lock = threading.Lock()
    state.ppr_config = MagicMock(damping_factor=0.70, max_iterations=20, tolerance=1e-7)
    state.signal_weights = {}
    state.exclude_seed_paths = exclude_seed_paths or ["tests/", "test_"]
    state.config_path = "/project/config.yaml"
    return state


def _make_context_result(**kwargs):
    defaults = dict(
        entity_name="login",
        entity_type="Function",
        qualified_name="/project/auth.py::login",
        file_path="/project/auth.py",
        line_start=10,
        line_end=20,
        relevance_score=0.9,
        source_code="def login(): pass",
        token_count=50,
    )
    defaults.update(kwargs)
    return ContextResult(**defaults)


def _make_core_result(**metadata_entry):
    meta = metadata_entry or {
        42: {"qname": "auth.py::login", "source": "entity_match"},
    }
    return RawRetrievalResult(
        seeds=PersonalizationVector(seeds={nid: 1.0 for nid in meta}, metadata=meta),
        ppr_results=[],
    )


# ---------------------------------------------------------------------------
# _graph_is_empty
# ---------------------------------------------------------------------------

class TestGraphIsEmpty:
    def test_empty_when_all_zero(self):
        state = _make_state()
        with patch("codegraph.mcp.tools.count_nodes_by_label", return_value={"Function": 0, "Class": 0}):
            assert _graph_is_empty(state) is True

    def test_not_empty_when_nodes_present(self):
        state = _make_state()
        with patch("codegraph.mcp.tools.count_nodes_by_label", return_value={"Function": 5, "Class": 2}):
            assert _graph_is_empty(state) is False

    def test_not_empty_on_query_exception(self):
        state = _make_state()
        with patch("codegraph.mcp.tools.count_nodes_by_label", side_effect=Exception("DB error")):
            assert _graph_is_empty(state) is False


# ---------------------------------------------------------------------------
# _start_background_index
# ---------------------------------------------------------------------------

class TestStartBackgroundIndex:
    def test_sets_indexing_in_progress(self):
        state = _make_state()
        with patch("threading.Thread") as MockThread:
            mock_thread = MagicMock()
            MockThread.return_value = mock_thread
            _start_background_index(state)
        assert state.indexing_in_progress is True

    def test_second_call_is_noop_when_already_indexing(self):
        state = _make_state(indexing_in_progress=True)
        with patch("threading.Thread") as MockThread:
            _start_background_index(state)
            MockThread.assert_not_called()

    def test_spawns_daemon_thread(self):
        state = _make_state()
        threads_started = []
        original_thread = threading.Thread

        def capture_thread(*args, **kwargs):
            t = original_thread(*args, **kwargs)
            threads_started.append(t)
            return t

        with patch("codegraph.mcp.tools.threading.Thread", side_effect=capture_thread):
            _start_background_index(state)

        assert len(threads_started) == 1
        assert threads_started[0].daemon is True


# ---------------------------------------------------------------------------
# get_relevant_context_impl
# ---------------------------------------------------------------------------

class TestGetRelevantContextImpl:
    def test_returns_json_with_summary_results_and_seeds(self):
        state = _make_state()
        result = _make_context_result()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", return_value=_make_core_result()),
            patch("codegraph.mcp.tools.format_context", return_value=[result]),
        ):
            output = get_relevant_context_impl("fix auth bug", None, None, 0, 0, state)

        payload = json.loads(output)
        assert "summary" in payload
        assert "results" in payload
        assert "seeds" in payload
        assert payload["summary"]["result_count"] == 1
        assert payload["results"][0]["entity_name"] == "login"
        assert payload["seeds"][0]["source"] == "entity_match"

    def test_empty_graph_triggers_background_index_and_returns_error(self):
        state = _make_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=True),
            patch("codegraph.mcp.tools._start_background_index") as mock_index,
        ):
            output = get_relevant_context_impl("task", None, None, 0, 0, state)

        mock_index.assert_called_once_with(state)
        payload = json.loads(output)
        assert "error" in payload
        assert "indexing" in payload["error"].lower()

    def test_pipeline_exception_returns_error_json(self):
        state = _make_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", side_effect=RuntimeError("GDS down")),
        ):
            output = get_relevant_context_impl("task", None, None, 0, 0, state)

        payload = json.loads(output)
        assert "error" in payload
        assert "detail" in payload
        assert "GDS down" in payload["detail"]

    def test_empty_core_result_returns_hint(self):
        state = _make_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", return_value=None),
        ):
            output = get_relevant_context_impl("task", None, None, 0, 0, state)

        payload = json.loads(output)
        assert payload["results"] == []
        assert "hint" in payload

    def test_empty_format_context_returns_hint(self):
        state = _make_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", return_value=_make_core_result()),
            patch("codegraph.mcp.tools.format_context", return_value=[]),
        ):
            output = get_relevant_context_impl("task", None, None, 0, 0, state)

        payload = json.loads(output)
        assert payload["results"] == []
        assert "hint" in payload

    def test_zero_top_k_uses_state_default(self):
        state = _make_state(default_top_k=25)
        result = _make_context_result()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", return_value=_make_core_result()) as mock_core,
            patch("codegraph.mcp.tools.format_context", return_value=[result]),
        ):
            get_relevant_context_impl("task", None, None, top_k=0, token_budget=0, state=state)

        call_kwargs = mock_core.call_args[1]
        assert call_kwargs["ppr_config"].top_k == 25

    def test_zero_budget_uses_state_default(self):
        state = _make_state(default_token_budget=8000)
        result = _make_context_result()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", return_value=_make_core_result()),
            patch("codegraph.mcp.tools.format_context", return_value=[result]) as mock_format,
        ):
            get_relevant_context_impl("task", None, None, top_k=5, token_budget=0, state=state)

        call_kwargs = mock_format.call_args[0]
        assert call_kwargs[2] == 8000

    def test_explicit_top_k_overrides_default(self):
        state = _make_state(default_top_k=30)
        result = _make_context_result()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", return_value=_make_core_result()) as mock_core,
            patch("codegraph.mcp.tools.format_context", return_value=[result]),
        ):
            get_relevant_context_impl("task", None, None, top_k=5, token_budget=0, state=state)

        call_kwargs = mock_core.call_args[1]
        assert call_kwargs["ppr_config"].top_k == 5

    def test_passes_exclude_seed_paths_from_state(self):
        state = _make_state(exclude_seed_paths=["tests/", "test_"])
        result = _make_context_result()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", return_value=_make_core_result()) as mock_core,
            patch("codegraph.mcp.tools.format_context", return_value=[result]),
        ):
            get_relevant_context_impl("task", None, None, 0, 0, state)

        call_kwargs = mock_core.call_args[1]
        assert call_kwargs["exclude_seed_paths"] == ["tests/", "test_"]

    def test_result_json_has_all_required_fields(self):
        state = _make_state()
        result = _make_context_result()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.run_core_retrieval", return_value=_make_core_result()),
            patch("codegraph.mcp.tools.format_context", return_value=[result]),
        ):
            output = get_relevant_context_impl("task", None, None, 0, 0, state)

        item = json.loads(output)["results"][0]
        assert "entity_name" in item
        assert "entity_type" in item
        assert "qualified_name" in item
        assert "file_path" in item
        assert "lines" in item
        assert "relevance_score" in item
        assert "token_count" in item
        assert "source_code" in item


# ---------------------------------------------------------------------------
# query_dependencies_impl
# ---------------------------------------------------------------------------

class TestQueryDependenciesImpl:
    def test_happy_path_returns_result_count_and_results(self):
        from codegraph.core.graph.queries import NodeInfoWithRel

        state = _make_state()
        node = NodeInfoWithRel(
            qualified_name="/project/auth.py::login",
            name="login",
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
        assert payload["results"][0]["name"] == "login"
        assert payload["results"][0]["relationship_type"] == "CALLS"

    def test_value_error_returns_error_json(self):
        state = _make_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch(
                "codegraph.mcp.tools.query_entity_dependencies",
                side_effect=ValueError("Invalid direction"),
            ),
        ):
            output = query_dependencies_impl("login", "sideways", 1, state)

        payload = json.loads(output)
        assert "error" in payload
        assert "Invalid direction" in payload["error"]

    def test_generic_exception_returns_error_with_detail(self):
        state = _make_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch(
                "codegraph.mcp.tools.query_entity_dependencies",
                side_effect=RuntimeError("DB timeout"),
            ),
        ):
            output = query_dependencies_impl("login", "both", 1, state)

        payload = json.loads(output)
        assert "error" in payload
        assert "detail" in payload
        assert "DB timeout" in payload["detail"]

    def test_empty_result_returns_hint(self):
        state = _make_state()

        with (
            patch("codegraph.mcp.tools._graph_is_empty", return_value=False),
            patch("codegraph.mcp.tools.query_entity_dependencies", return_value=[]),
        ):
            output = query_dependencies_impl("ghost", "both", 1, state)

        payload = json.loads(output)
        assert payload["result_count"] == 0
        assert "hint" in payload

    def test_file_paths_made_relative(self):
        from codegraph.core.graph.queries import NodeInfoWithRel

        state = _make_state(project_root="/project")
        node = NodeInfoWithRel(
            qualified_name="/project/auth.py::login",
            name="login",
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
        assert payload["results"][0]["file_path"] == "auth.py"
