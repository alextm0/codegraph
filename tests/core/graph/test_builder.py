"""Tests for src/graph/graph_builder.py — batch node and edge creation."""

from pathlib import Path

import pytest

from codegraph.core.parser.python_parser import create_parser, parse_directory
from codegraph.core.graph.graph_builder import build_graph, clear_database, EDGE_WEIGHTS
from codegraph.core.graph.queries import count_nodes_by_label, count_edges_by_type
from tests.conftest import neo4j_required

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"
USER_AUTH = str(FIXTURES_DIR / "user_auth")


@pytest.fixture(scope="module")
def parser():
    return create_parser()


@pytest.fixture(scope="module")
def user_auth_entities(parser):
    """Parse the user_auth fixture once for the whole module."""
    return parse_directory(USER_AUTH, parser)


# ---------------------------------------------------------------------------
# EDGE_WEIGHTS
# ---------------------------------------------------------------------------

def test_edge_weights_contains_all_types():
    """EDGE_WEIGHTS must define weights for all four relationship types."""
    assert set(EDGE_WEIGHTS.keys()) == {"INHERITS_FROM", "CALLS", "IMPORTS", "CONTAINS"}


def test_edge_weights_values_are_floats_in_range():
    """Every weight must be a float between 0 and 1 (inclusive)."""
    for rel_type, weight in EDGE_WEIGHTS.items():
        assert isinstance(weight, float), f"{rel_type} weight is not a float"
        assert 0.0 <= weight <= 1.0, f"{rel_type} weight {weight} out of range"


# ---------------------------------------------------------------------------
# build_graph — empty input
# ---------------------------------------------------------------------------

@neo4j_required
def test_build_graph_empty_input(clean_db):
    """build_graph with an empty list must return zero counts without raising."""
    counts = build_graph(clean_db, [])
    assert counts["File"] == 0
    assert counts["Function"] == 0
    assert counts["Class"] == 0
    assert counts["Method"] == 0


# ---------------------------------------------------------------------------
# clear_database
# ---------------------------------------------------------------------------

@neo4j_required
def test_clear_database_removes_all_nodes(clean_db, user_auth_entities):
    """After build + clear, the database must have zero nodes."""
    build_graph(clean_db, user_auth_entities)
    count_before = sum(count_nodes_by_label(clean_db).values())
    assert count_before > 0

    clear_database(clean_db)
    count_after = sum(count_nodes_by_label(clean_db).values())
    assert count_after == 0


# ---------------------------------------------------------------------------
# build_graph — node counts
# ---------------------------------------------------------------------------

@neo4j_required
def test_build_graph_returns_count_dict(clean_db, user_auth_entities):
    """build_graph must return a dict with counts for each node and edge type."""
    counts = build_graph(clean_db, user_auth_entities)
    assert isinstance(counts, dict)
    for key in ("File", "Function", "Class", "Method"):
        assert key in counts, f"Missing key '{key}' in counts"


@neo4j_required
def test_build_graph_creates_correct_file_node_count(clean_db, user_auth_entities):
    """user_auth fixture has exactly 7 .py files -> 7 File nodes."""
    build_graph(clean_db, user_auth_entities)
    label_counts = count_nodes_by_label(clean_db)
    assert label_counts.get("File", 0) == 7


@neo4j_required
def test_build_graph_creates_correct_class_node_count(clean_db, user_auth_entities):
    """user_auth fixture has BaseModel, User, AuthService -> 3 Class nodes."""
    build_graph(clean_db, user_auth_entities)
    label_counts = count_nodes_by_label(clean_db)
    assert label_counts.get("Class", 0) == 3


@neo4j_required
def test_build_graph_creates_method_nodes(clean_db, user_auth_entities):
    """user_auth fixture has exactly 9 methods across all classes."""
    build_graph(clean_db, user_auth_entities)
    label_counts = count_nodes_by_label(clean_db)
    assert label_counts.get("Method", 0) == 9


@neo4j_required
def test_build_graph_creates_function_nodes(clean_db, user_auth_entities):
    """user_auth fixture has 4 validators + 1 create_guest_user = 5 top-level functions."""
    build_graph(clean_db, user_auth_entities)
    label_counts = count_nodes_by_label(clean_db)
    assert label_counts.get("Function", 0) == 5


# ---------------------------------------------------------------------------
# build_graph — edge counts
# ---------------------------------------------------------------------------

@neo4j_required
def test_build_graph_creates_contains_edges(clean_db, user_auth_entities):
    """5 File->Function + 3 File->Class + 9 Class->Method = 17 CONTAINS edges."""
    build_graph(clean_db, user_auth_entities)
    edge_counts = count_edges_by_type(clean_db)
    assert edge_counts.get("CONTAINS", 0) == 17


@neo4j_required
def test_build_graph_creates_inherits_from_edge(clean_db, user_auth_entities):
    """User inherits from BaseModel -> exactly 1 INHERITS_FROM edge."""
    build_graph(clean_db, user_auth_entities)
    edge_counts = count_edges_by_type(clean_db)
    assert edge_counts.get("INHERITS_FROM", 0) == 1


@neo4j_required
def test_build_graph_creates_calls_edges(clean_db, user_auth_entities):
    """register->3 validators + register->User + create_guest_user->User + validate_password->validate_password_strength = 6."""
    build_graph(clean_db, user_auth_entities)
    edge_counts = count_edges_by_type(clean_db)
    assert edge_counts.get("CALLS", 0) == 6


@neo4j_required
def test_build_graph_creates_imports_edges(clean_db, user_auth_entities):
    """models/__init__->user + auth_service->user + auth_service->validators = 3."""
    build_graph(clean_db, user_auth_entities)
    edge_counts = count_edges_by_type(clean_db)
    assert edge_counts.get("IMPORTS", 0) == 3


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

@neo4j_required
def test_build_graph_is_idempotent(clean_db, user_auth_entities):
    """Calling build_graph twice must not duplicate nodes (MERGE semantics)."""
    build_graph(clean_db, user_auth_entities)
    counts_first = count_nodes_by_label(clean_db)

    build_graph(clean_db, user_auth_entities)
    counts_second = count_nodes_by_label(clean_db)

    assert counts_first == counts_second
