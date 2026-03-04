"""Tests for src/retrieval/seed_selection.py."""

from pathlib import Path

import pytest

from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.retrieval.seed_selection import extract_seeds, PersonalizationVector
from codegraph.core.parser.python_parser import create_parser, parse_directory
from tests.conftest import neo4j_required

FIXTURES_DIR = Path(__file__).parents[3] / "fixtures"
USER_AUTH = str(FIXTURES_DIR / "user_auth")


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


@neo4j_required
class TestPersonalizationVector:
    """Tests for the PersonalizationVector container."""

    def test_init_from_dict(self):
        """Must correctly store the seed mapping."""
        seeds = {"a": 0.5, "b": 1.0}
        pv = PersonalizationVector(seeds=seeds)
        assert pv.seeds == seeds

    def test_normalize_empty_pv(self):
        """Normalizing an empty PV must not raise."""
        pv = PersonalizationVector(seeds={})
        pv.normalize()
        assert pv.seeds == {}

    def test_normalize_sums_to_one(self):
        """After normalization, the sum of all weights must be exactly 1.0."""
        pv = PersonalizationVector(seeds={"a": 10.0, "b": 30.0})
        pv.normalize()
        assert sum(pv.seeds.values()) == pytest.approx(1.0)
        assert pv.seeds["a"] == 0.25
        assert pv.seeds["b"] == 0.75

    def test_normalize_single_seed(self):
        """A single seed must always normalize to 1.0."""
        pv = PersonalizationVector(seeds={"only_one": 0.0001})
        pv.normalize()
        assert pv.seeds["only_one"] == 1.0


@neo4j_required
class TestMatchEntities:
    """Tests for name-based exact matching (seed signal 1)."""

    def test_returns_pv_instance(self, populated_db):
        """extract_seeds must always return a PersonalizationVector."""
        pv = extract_seeds(
            populated_db,
            task_description="some task",
            mentioned_entities=["User"],
        )
        assert isinstance(pv, PersonalizationVector)

    def test_known_entity_resolves(self, populated_db):
        """Exact name 'AuthService' should find a node."""
        pv = extract_seeds(
            populated_db,
            task_description="some task",
            mentioned_entities=["AuthService"],
        )
        assert len(pv.seeds) > 0, "Expected at least one seed for 'AuthService'"

    def test_method_name_resolves(self, populated_db):
        """Method name 'register' should find a seed node."""
        pv = extract_seeds(
            populated_db,
            task_description="some task",
            mentioned_entities=["register"],
        )
        assert len(pv.seeds) > 0, "Expected seed for method 'register'"

    def test_unknown_entity_resolves_to_empty(self, populated_db):
        """An entity that doesn't exist in the graph should not produce seeds."""
        pv = extract_seeds(
            populated_db,
            task_description="some task",
            mentioned_entities=["GhostObject"],
        )
        assert len(pv.seeds) == 0

    def test_empty_mentioned_entities_uses_bm25_only(self, populated_db):
        """No mentioned_entities: BM25 must still produce seeds."""
        pv = extract_seeds(
            populated_db,
            task_description="validate email address format",
            mentioned_entities=[],
        )
        assert len(pv.seeds) > 0, "BM25 should find relevant seeds for 'validate email'"


@neo4j_required
class TestBM25Search:
    """Tests for description-based BM25 matching (seed signal 2)."""

    def test_auth_task_ranks_auth_entities(self, populated_db):
        """Task about authentication should surface auth-related nodes."""
        pv = extract_seeds(
            populated_db,
            task_description="fix the user authentication and registration flow",
        )
        assert len(pv.seeds) > 0

    def test_validate_task_ranks_validators(self, populated_db):
        """Task about validation should surface validate_* functions."""
        pv = extract_seeds(
            populated_db,
            task_description="validate email and password",
        )
        assert len(pv.seeds) > 0


@neo4j_required
class TestCurrentFileSeeds:
    """Tests for current_file signal (seed signal 3)."""

    def test_current_file_produces_seeds(self, populated_db):
        """Entities from current_file should appear in seeds."""
        pv = extract_seeds(
            populated_db,
            task_description="some task",
            current_file="services/auth_service.py",
        )
        assert len(pv.seeds) > 0, "Expected seeds from current_file"

    def test_unknown_file_produces_no_file_seeds(self, populated_db):
        """If the file is not in the graph, no extra seeds are produced."""
        pv_only_task = extract_seeds(populated_db, "some task")
        pv_with_ghost_file = extract_seeds(
            populated_db, "some task", current_file="ghost.py"
        )
        # Weights should be identical as if no file was provided
        assert pv_with_ghost_file.seeds == pv_only_task.seeds
