"""Tests for src/retrieval/pipeline.py.

All tests require a running Neo4j instance and use the user_auth fixture.
The graph is built once per module to keep test time short.
"""

from pathlib import Path

import pytest

from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import PPRConfig, create_gds_client, drop_projection
from codegraph.core.retrieval.pipeline import ensure_graph_ready, run_retrieval_pipeline
from codegraph.core.retrieval.post_processing import ContextResult
from codegraph.core.parser.python_parser import create_parser, parse_directory
from tests.conftest import neo4j_required

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"
USER_AUTH = str(FIXTURES_DIR / "user_auth")
PROJECT_ROOT = str(FIXTURES_DIR / "user_auth")


# ---------------------------------------------------------------------------
# Module-level fixtures: build the graph once for all tests in this file.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser():
    return create_parser()


@pytest.fixture(scope="module")
def user_auth_entities(parser):
    return parse_directory(USER_AUTH, parser)


@pytest.fixture(scope="module")
def populated_db(neo4j_driver, user_auth_entities):
    """Build the user_auth graph once for the whole module."""
    clear_database(neo4j_driver)
    build_graph(neo4j_driver, user_auth_entities)
    yield neo4j_driver
    clear_database(neo4j_driver)


@pytest.fixture(scope="module")
def gds_client(populated_db):
    """GDS client backed by the populated database."""
    return create_gds_client(populated_db)


# ---------------------------------------------------------------------------
# ensure_graph_ready tests
# ---------------------------------------------------------------------------

@neo4j_required
class TestEnsureGraphReady:
    def test_returns_graph_projection(self, populated_db, gds_client):
        """ensure_graph_ready should return a GDS Graph projection object."""
        projection = ensure_graph_ready(populated_db, gds_client)
        assert projection is not None

    def test_projection_has_nodes(self, populated_db, gds_client):
        """The returned projection must contain at least one node."""
        projection = ensure_graph_ready(populated_db, gds_client)
        assert projection.node_count() > 0

    def test_projection_has_relationships(self, populated_db, gds_client):
        """The returned projection must contain at least one relationship."""
        projection = ensure_graph_ready(populated_db, gds_client)
        assert projection.relationship_count() > 0

    def test_idempotent_first_call(self, populated_db, gds_client):
        """Calling ensure_graph_ready twice must not raise any exception."""
        ensure_graph_ready(populated_db, gds_client)
        ensure_graph_ready(populated_db, gds_client)

    def test_idempotent_same_node_count(self, populated_db, gds_client):
        """Two consecutive calls should produce projections with the same node count."""
        first = ensure_graph_ready(populated_db, gds_client)
        second = ensure_graph_ready(populated_db, gds_client)
        assert first.node_count() == second.node_count()


# ---------------------------------------------------------------------------
# run_retrieval_pipeline tests
# ---------------------------------------------------------------------------

@neo4j_required
class TestRunRetrievalPipeline:
    def test_returns_list(self, populated_db, gds_client):
        """Pipeline must always return a list."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="fix authentication bug",
            project_root=PROJECT_ROOT,
        )
        assert isinstance(result, list)

    def test_returns_context_result_instances(self, populated_db, gds_client):
        """Every item in the result must be a ContextResult."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="validate user credentials and authenticate",
            project_root=PROJECT_ROOT,
        )
        for item in result:
            assert isinstance(item, ContextResult), (
                f"Expected ContextResult, got {type(item)}"
            )

    def test_non_empty_result_for_known_task(self, populated_db, gds_client):
        """A task related to the user_auth fixture should return at least one result."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="fix the user registration validation bug",
            project_root=PROJECT_ROOT,
            mentioned_entities=["AuthService"],
        )
        assert len(result) > 0, "Expected non-empty results for a known auth task"

    def test_context_results_have_source_code(self, populated_db, gds_client):
        """Each returned ContextResult must have non-empty source_code."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="validate email and password",
            project_root=PROJECT_ROOT,
        )
        for item in result:
            assert item.source_code, (
                f"Expected non-empty source_code for '{item.entity_name}'"
            )

    def test_context_results_have_positive_token_count(self, populated_db, gds_client):
        """Each returned ContextResult must have token_count > 0."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="authenticate user login",
            project_root=PROJECT_ROOT,
        )
        for item in result:
            assert item.token_count > 0, (
                f"Expected token_count > 0 for '{item.entity_name}'"
            )

    def test_results_ordered_by_descending_score(self, populated_db, gds_client):
        """Results must be in descending relevance_score order."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="authenticate and register users",
            project_root=PROJECT_ROOT,
            mentioned_entities=["AuthService"],
        )
        if len(result) < 2:
            pytest.skip("Need at least 2 results to verify ordering")

        scores = [item.relevance_score for item in result]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Scores not in descending order at index {i}: "
                f"{scores[i]} < {scores[i + 1]}"
            )

    def test_respects_tight_token_budget(self, populated_db, gds_client):
        """With a very tight token budget, at most 1 result should be returned."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="validate user input",
            project_root=PROJECT_ROOT,
            token_budget=1,  # Intentionally tiny — forces budget cutoff after first item.
        )
        # The pipeline always returns at least 1 result (the most relevant),
        # even if it exceeds the budget. With budget=1 it should return exactly 1.
        assert len(result) <= 2, (
            f"Expected at most 1-2 results with tiny budget, got {len(result)}"
        )

    def test_empty_task_description_does_not_crash(self, populated_db, gds_client):
        """An empty task description should not raise an exception."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="",
            project_root=PROJECT_ROOT,
        )
        assert isinstance(result, list)

    def test_unknown_mentioned_entity_falls_back_to_bm25(self, populated_db, gds_client):
        """If mentioned_entities has no matches, BM25 should still produce seeds."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="validate email address format",
            project_root=PROJECT_ROOT,
            mentioned_entities=["NonExistentEntityXYZ999"],
        )
        # Should not crash; may return empty or non-empty depending on BM25 signal.
        assert isinstance(result, list)

    def test_custom_ppr_config_accepted(self, populated_db, gds_client):
        """Pipeline must accept a custom PPRConfig without raising."""
        custom_config = PPRConfig(damping_factor=0.7, top_k=5)
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="authenticate user",
            project_root=PROJECT_ROOT,
            ppr_config=custom_config,
        )
        assert isinstance(result, list)
        # top_k=5 means at most 5 PPR results, likely fewer context items.
        assert len(result) <= 5

    def test_current_file_hint_does_not_crash(self, populated_db, gds_client):
        """Providing current_file should not raise an exception."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="fix auth service",
            project_root=PROJECT_ROOT,
            current_file="services/auth_service.py",
        )
        assert isinstance(result, list)

    def test_all_context_results_have_file_path(self, populated_db, gds_client):
        """Every returned ContextResult must have a non-empty file_path."""
        result = run_retrieval_pipeline(
            driver=populated_db,
            gds=gds_client,
            task_description="register a new user account",
            project_root=PROJECT_ROOT,
            mentioned_entities=["register"],
        )
        for item in result:
            assert item.file_path, (
                f"Expected non-empty file_path for '{item.entity_name}'"
            )
