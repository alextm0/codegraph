"""Tests for src/retrieval/post_processing.py."""

from pathlib import Path

import pytest

from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.retrieval.post_processing import apply_idf_weights
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
