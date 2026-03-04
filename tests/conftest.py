"""Shared pytest fixtures for graph tests.

Requires a running Neo4j instance at bolt://localhost:7687 with default credentials.
Tests that need Neo4j are marked with @pytest.mark.neo4j and are skipped when
the database is not reachable.
"""

from pathlib import Path

import pytest
from neo4j.exceptions import ServiceUnavailable, AuthError

from codegraph.core.graph.connection import load_config, Neo4jConfig, create_driver, verify_connectivity, close_driver

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# ---------------------------------------------------------------------------
# Neo4j availability check
# ---------------------------------------------------------------------------

def _neo4j_available() -> bool:
    """Return True if the test Neo4j instance is reachable.

    Configuration errors (bad config.yaml, missing keys) are re-raised so they
    fail loudly. Only genuine connection failures return False.
    """
    config = load_config(_CONFIG_PATH)
    try:
        driver = create_driver(config)
        ok = verify_connectivity(driver)
        close_driver(driver)
        return ok
    except (ServiceUnavailable, AuthError, OSError, ConnectionError):
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
    """Return the Neo4j config loaded from config.yaml."""
    return load_config(_CONFIG_PATH)


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
    from codegraph.core.graph.graph_builder import clear_database
    clear_database(neo4j_driver)
    yield neo4j_driver
    clear_database(neo4j_driver)
