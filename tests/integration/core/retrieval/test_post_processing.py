"""Tests for src/retrieval/post_processing.py."""

from pathlib import Path

import pytest

from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import PPRResult
from codegraph.core.retrieval.post_processing import apply_idf_weights, _deduplicate_file_entities
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


def _make_ppr(label: str, file_path: str, name: str = "", score: float = 1.0) -> PPRResult:
    """Helper to construct minimal PPRResult fixtures."""
    return PPRResult(
        qualified_name=f"{file_path}::{name}" if name else file_path,
        name=name or file_path,
        label=label,
        file_path=file_path,
        score=score,
    )


class TestDeduplicateFileEntities:
    """Unit tests for _deduplicate_file_entities — no Neo4j required."""

    def test_file_with_two_sub_entities_is_dropped(self):
        """File node dropped when 2+ sub-entities from same file are present."""
        results = [
            _make_ppr("Function", "blog.py", "get_post", score=0.9),
            _make_ppr("File", "blog.py", score=0.8),
            _make_ppr("Function", "blog.py", "update", score=0.7),
        ]
        deduped = _deduplicate_file_entities(results)
        labels = [r.label for r in deduped]
        assert "File" not in labels
        assert len(deduped) == 2

    def test_file_with_one_sub_entity_is_kept(self):
        """File node kept when only one sub-entity from that file exists."""
        results = [
            _make_ppr("Function", "auth.py", "login", score=0.9),
            _make_ppr("File", "auth.py", score=0.8),
        ]
        deduped = _deduplicate_file_entities(results)
        assert len(deduped) == 2  # both kept

    def test_file_with_no_sub_entities_is_kept(self):
        """File node kept when no sub-entities from that file exist."""
        results = [_make_ppr("File", "models.py", score=0.9)]
        deduped = _deduplicate_file_entities(results)
        assert len(deduped) == 1

    def test_different_files_not_affected(self):
        """Sub-entities from file A do not cause file B to be dropped."""
        results = [
            _make_ppr("Function", "auth.py", "login", score=0.9),
            _make_ppr("Function", "auth.py", "logout", score=0.8),
            _make_ppr("File", "models.py", score=0.7),  # different file — keep
        ]
        deduped = _deduplicate_file_entities(results)
        file_paths = [r.file_path for r in deduped if r.label == "File"]
        assert "models.py" in file_paths

    def test_empty_input(self):
        """Empty list returns empty list without error."""
        assert _deduplicate_file_entities([]) == []

    def test_order_preserved(self):
        """Deduplication preserves the original ranking order."""
        results = [
            _make_ppr("Function", "blog.py", "get_post", score=0.9),
            _make_ppr("File", "blog.py", score=0.8),
            _make_ppr("Function", "blog.py", "update", score=0.7),
            _make_ppr("Class", "models.py", "User", score=0.5),
        ]
        deduped = _deduplicate_file_entities(results)
        scores = [r.score for r in deduped]
        assert scores == sorted(scores, reverse=True)


@neo4j_required
class TestApplyIdfWeights:
    """Tests for the IDF-based edge weight adjustment."""

    def test_returns_int(self, populated_db):
        """apply_idf_weights must return the count of updated edges."""
        updated = apply_idf_weights(populated_db)
        assert isinstance(updated, int)

    def test_edges_updated(self, populated_db):
        """With user_auth graph (27 edges), at least some edges should be updated."""
        updated = apply_idf_weights(populated_db)
        assert updated > 0, f"Expected edges to be updated, got {updated}"

    def test_idempotent_calls(self, populated_db):
        """Calling twice is fine; second call should update 0 or 27 edges again."""
        first = apply_idf_weights(populated_db)
        second = apply_idf_weights(populated_db)
        # Second call should find the same edges and 'update' them to the same value
        assert second == first
