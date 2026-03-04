"""Tests for src/graph/ppr.py — GDS projection and Personalized PageRank."""

from pathlib import Path

import pytest

from codegraph.core.parser.python_parser import create_parser, parse_directory
from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import (
    PPRConfig,
    PPRResult,
    create_gds_client,
    project_graph,
    drop_projection,
    run_ppr,
)
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
    """Build graph once for the whole module."""
    clear_database(neo4j_driver)
    build_graph(neo4j_driver, user_auth_entities)
    yield neo4j_driver
    clear_database(neo4j_driver)


@pytest.fixture(scope="module")
def gds_client(neo4j_driver):
    """GDS client backed by the session driver."""
    return create_gds_client(neo4j_driver)


@pytest.fixture()
def projected(populated_db, gds_client):
    """Function-scoped fixture: project graph before test, drop it after."""
    project_graph(gds_client)
    yield gds_client
    drop_projection(gds_client)


# ---------------------------------------------------------------------------
# PPRConfig
# ---------------------------------------------------------------------------

def test_ppr_config_defaults():
    """Default PPRConfig values match the spec."""
    cfg = PPRConfig()
    assert cfg.damping_factor == 0.85
    assert cfg.max_iterations == 20
    assert cfg.tolerance == 1e-7
    assert cfg.top_k == 20


def test_ppr_config_is_frozen():
    """PPRConfig must be immutable."""
    cfg = PPRConfig()
    with pytest.raises((AttributeError, TypeError)):
        cfg.top_k = 5  # type: ignore[misc]


def test_ppr_config_custom():
    """Custom values are stored correctly."""
    cfg = PPRConfig(damping_factor=0.9, max_iterations=10, tolerance=1e-5, top_k=5)
    assert cfg.damping_factor == 0.9
    assert cfg.top_k == 5


# ---------------------------------------------------------------------------
# PPRResult
# ---------------------------------------------------------------------------

def test_ppr_result_is_frozen():
    """PPRResult must be immutable."""
    r = PPRResult(qualified_name="a::b", name="b", label="Function", file_path="a.py", score=0.5)
    with pytest.raises((AttributeError, TypeError)):
        r.score = 1.0  # type: ignore[misc]


def test_ppr_result_fields():
    """PPRResult stores all five fields correctly."""
    r = PPRResult(qualified_name="a::b", name="b", label="Method", file_path="a.py", score=0.42)
    assert r.qualified_name == "a::b"
    assert r.score == 0.42


# ---------------------------------------------------------------------------
# create_gds_client
# ---------------------------------------------------------------------------

@neo4j_required
def test_create_gds_client_returns_object(neo4j_driver):
    """create_gds_client should not raise and return a non-None object."""
    client = create_gds_client(neo4j_driver)
    assert client is not None


# ---------------------------------------------------------------------------
# project_graph / drop_projection
# ---------------------------------------------------------------------------

@neo4j_required
def test_project_graph_creates_projection(projected):
    """project_graph must create the in-memory projection without raising."""
    # projected fixture already called project_graph; just assert it returned non-None
    assert projected is not None


@neo4j_required
def test_drop_projection_returns_true_when_exists(populated_db, gds_client):
    """drop_projection returns True when the projection exists."""
    project_graph(gds_client)
    existed = drop_projection(gds_client)
    assert existed is True


@neo4j_required
def test_drop_projection_returns_false_when_not_exists(gds_client):
    """drop_projection returns False when no projection exists."""
    drop_projection(gds_client)  # ensure it's gone
    existed = drop_projection(gds_client)
    assert existed is False


# ---------------------------------------------------------------------------
# run_ppr
# ---------------------------------------------------------------------------

@neo4j_required
def test_run_ppr_returns_list(projected, neo4j_driver):
    """run_ppr must return a list."""
    results = run_ppr(projected, neo4j_driver, ["AuthService.register"])
    assert isinstance(results, list)


@neo4j_required
def test_run_ppr_results_are_ppr_result_objects(projected, neo4j_driver):
    """All items returned by run_ppr must be PPRResult instances."""
    results = run_ppr(projected, neo4j_driver, ["AuthService.register"])
    for item in results:
        assert isinstance(item, PPRResult)


@neo4j_required
def test_run_ppr_scores_are_positive(projected, neo4j_driver):
    """PPR scores must be non-negative."""
    results = run_ppr(projected, neo4j_driver, ["AuthService.register"])
    for item in results:
        assert item.score >= 0.0


@neo4j_required
def test_run_ppr_respects_top_k(projected, neo4j_driver):
    """run_ppr must return at most top_k results."""
    cfg = PPRConfig(top_k=3)
    results = run_ppr(projected, neo4j_driver, ["AuthService.register"], config=cfg)
    assert len(results) <= 3


@neo4j_required
def test_run_ppr_sorted_descending(projected, neo4j_driver):
    """PPR results must be sorted by score in descending order."""
    results = run_ppr(projected, neo4j_driver, ["AuthService.register"])
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


@neo4j_required
def test_run_ppr_unknown_seed_returns_empty(projected, neo4j_driver):
    """run_ppr with an unknown seed name must return an empty list."""
    results = run_ppr(projected, neo4j_driver, ["NonExistentSeedNodeXYZ"])
    assert results == []


@neo4j_required
def test_run_ppr_auth_service_register_ranks_validators_highly(projected, neo4j_driver):
    """Seeding from AuthService.register should rank validator functions highly."""
    results = run_ppr(projected, neo4j_driver, ["AuthService.register"], config=PPRConfig(top_k=10))
    top_names = {r.name for r in results}
    # At least one validator should appear in top-10
    validators = {"validate_email", "validate_username", "validate_password"}
    assert top_names & validators, f"No validators in top results: {top_names}"
