"""Shared pytest fixtures for graph tests.

Requires a running Neo4j instance at bolt://localhost:7687 with default credentials.
Tests that need Neo4j are marked with @pytest.mark.neo4j and are skipped when
the database is not reachable.
"""

import pytest

from src.graph.connection import Neo4jConfig, create_driver, verify_connectivity, close_driver

# ---------------------------------------------------------------------------
# Neo4j availability check
# ---------------------------------------------------------------------------

def _neo4j_available() -> bool:
    """Return True if the test Neo4j instance is reachable."""
    config = Neo4jConfig()
    try:
        driver = create_driver(config)
        ok = verify_connectivity(driver)
        close_driver(driver)
        return ok
    except Exception:
        return False


_NEO4J_AVAILABLE = _neo4j_available()

neo4j_required = pytest.mark.skipif(
    not _NEO4J_AVAILABLE,
    reason="Neo4j not reachable at bolt://localhost:7687",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def neo4j_config() -> Neo4jConfig:
    """Return the default test Neo4j config."""
    return Neo4jConfig()


@pytest.fixture(scope="session")
def neo4j_driver(neo4j_config):
    """Session-scoped Neo4j driver. Skips if Neo4j is not reachable."""
    if not _NEO4J_AVAILABLE:
        pytest.skip("Neo4j not reachable")
    driver = create_driver(neo4j_config)
    yield driver
    close_driver(driver)


@pytest.fixture
def clean_db(neo4j_driver):
    """Wipe the database before (and after) each test that uses it."""
    from src.graph.graph_builder import clear_database
    clear_database(neo4j_driver)
    yield neo4j_driver
    clear_database(neo4j_driver)
