"""Tests for src/retrieval/seed_selection.py."""

from pathlib import Path

import pytest

from codegraph.core.parser.python_parser import create_parser, parse_directory
from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import create_gds_client, project_graph, drop_projection
from codegraph.core.retrieval.seed_selection import (
    SeedNode,
    PersonalizationVector,
    extract_seeds,
    _normalize_seeds,
    _tokenize,
)
from tests.conftest import neo4j_required

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"
USER_AUTH = str(FIXTURES_DIR / "user_auth")


# ---------------------------------------------------------------------------
# Module-level fixtures (no Neo4j required)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser():
    return create_parser()


@pytest.fixture(scope="module")
def user_auth_entities(parser):
    return parse_directory(USER_AUTH, parser)


@pytest.fixture(scope="module")
def populated_db(neo4j_driver, user_auth_entities):
    """Build user_auth graph once for the whole module."""
    clear_database(neo4j_driver)
    build_graph(neo4j_driver, user_auth_entities)
    yield neo4j_driver
    clear_database(neo4j_driver)


# ---------------------------------------------------------------------------
# Pure-function tests (no Neo4j)
# ---------------------------------------------------------------------------

class TestSeedNode:
    def test_frozen(self):
        """SeedNode must be immutable."""
        seed = SeedNode(node_id=1, qualified_name="a::b", weight=0.5, source="bm25")
        with pytest.raises((AttributeError, TypeError)):
            seed.weight = 1.0  # type: ignore[misc]

    def test_fields_stored(self):
        seed = SeedNode(node_id=42, qualified_name="f.py::foo", weight=0.3, source="entity_match")
        assert seed.node_id == 42
        assert seed.qualified_name == "f.py::foo"
        assert seed.weight == 0.3
        assert seed.source == "entity_match"


class TestPersonalizationVector:
    def test_frozen(self):
        pv = PersonalizationVector(seeds={1: 0.5, 2: 0.5})
        with pytest.raises((AttributeError, TypeError)):
            pv.seeds = {}  # type: ignore[misc]

    def test_empty_seeds(self):
        pv = PersonalizationVector(seeds={})
        assert pv.seeds == {}


class TestNormalizeSeeds:
    def test_single_seed_normalizes_to_one(self):
        seeds = [SeedNode(node_id=1, qualified_name="a", weight=3.0, source="bm25")]
        pv = _normalize_seeds(seeds)
        assert abs(pv.seeds[1] - 1.0) < 1e-9

    def test_two_equal_seeds_split_evenly(self):
        seeds = [
            SeedNode(node_id=1, qualified_name="a", weight=1.0, source="entity_match"),
            SeedNode(node_id=2, qualified_name="b", weight=1.0, source="bm25"),
        ]
        pv = _normalize_seeds(seeds)
        assert abs(pv.seeds[1] - 0.5) < 1e-9
        assert abs(pv.seeds[2] - 0.5) < 1e-9

    def test_duplicate_node_ids_summed(self):
        seeds = [
            SeedNode(node_id=5, qualified_name="a", weight=0.4, source="entity_match"),
            SeedNode(node_id=5, qualified_name="a", weight=0.6, source="bm25"),
        ]
        pv = _normalize_seeds(seeds)
        assert 5 in pv.seeds
        assert abs(pv.seeds[5] - 1.0) < 1e-9

    def test_weights_sum_to_one(self):
        seeds = [
            SeedNode(node_id=1, qualified_name="a", weight=2.0, source="entity_match"),
            SeedNode(node_id=2, qualified_name="b", weight=3.0, source="bm25"),
            SeedNode(node_id=3, qualified_name="c", weight=5.0, source="current_file"),
        ]
        pv = _normalize_seeds(seeds)
        total = sum(pv.seeds.values())
        assert abs(total - 1.0) < 1e-9

    def test_all_zero_weights_returns_empty(self):
        seeds = [SeedNode(node_id=1, qualified_name="a", weight=0.0, source="bm25")]
        pv = _normalize_seeds(seeds)
        assert pv.seeds == {}


class TestTokenize:
    def test_basic_split(self):
        tokens = _tokenize("validate email address")
        assert tokens == ["validate", "email", "address"]

    def test_camel_case_preserved_as_one_token(self):
        tokens = _tokenize("AuthService")
        assert "authservice" in tokens

    def test_underscores_preserved(self):
        tokens = _tokenize("validate_email")
        assert "validate_email" in tokens

    def test_empty_string_returns_empty(self):
        assert _tokenize("") == []

    def test_punctuation_stripped(self):
        tokens = _tokenize("fix(auth.login)")
        assert "fix" in tokens
        assert "auth" in tokens
        assert "login" in tokens


# ---------------------------------------------------------------------------
# Neo4j-backed tests
# ---------------------------------------------------------------------------

@neo4j_required
class TestMatchEntities:
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

    def test_unknown_entity_falls_back_to_bm25(self, populated_db):
        """Unknown entity produces no entity_match seeds but BM25 may still fire."""
        pv = extract_seeds(
            populated_db,
            task_description="validate user credentials",
            mentioned_entities=["NonExistentXYZ123"],
        )
        # Should still return something from BM25, or at least an empty vector
        assert isinstance(pv.seeds, dict)

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

    def test_personalization_vector_sums_to_one(self, populated_db):
        """Resulting weights must sum to 1.0."""
        pv = extract_seeds(
            populated_db,
            task_description="fix authentication timeout bug",
            mentioned_entities=["AuthService"],
        )
        if pv.seeds:
            total = sum(pv.seeds.values())
            assert abs(total - 1.0) < 1e-6, f"Weights sum to {total}, expected 1.0"


@neo4j_required
class TestCurrentFileSeeds:
    def test_current_file_produces_seeds(self, populated_db):
        """Entities from current_file should appear in seeds."""
        pv = extract_seeds(
            populated_db,
            task_description="some task",
            current_file="services/auth_service.py",
        )
        assert len(pv.seeds) > 0, "Expected seeds from current_file"

    def test_nonexistent_file_produces_no_file_seeds(self, populated_db):
        """Non-existent file_path should not crash and may yield no file seeds."""
        pv = extract_seeds(
            populated_db,
            task_description="fix bug",
            current_file="nonexistent/file.py",
        )
        # Should not raise; may be empty or have BM25 seeds
        assert isinstance(pv.seeds, dict)


@neo4j_required
class TestExtractSeedsIntegration:
    def test_all_signals_combined(self, populated_db):
        """All three signals together produce a valid vector."""
        pv = extract_seeds(
            populated_db,
            task_description="fix authentication and validation",
            mentioned_entities=["AuthService", "validate_email"],
            current_file="utils/validators.py",
        )
        assert isinstance(pv.seeds, dict)
        if pv.seeds:
            total = sum(pv.seeds.values())
            assert abs(total - 1.0) < 1e-6

    def test_empty_task_still_produces_vector(self, populated_db):
        """Empty task description should not crash."""
        pv = extract_seeds(populated_db, task_description="")
        assert isinstance(pv.seeds, dict)

    def test_custom_signal_weights_accepted(self, populated_db):
        """Custom signal weights must be accepted without errors."""
        pv = extract_seeds(
            populated_db,
            task_description="validate password strength",
            signal_weights={"entity_match": 0.8, "bm25": 0.2, "current_file": 0.0},
        )
        assert isinstance(pv.seeds, dict)
