"""Shared pytest fixtures for graph tests.

Requires a running Neo4j instance at bolt://localhost:7687 with default credentials.
Tests that need Neo4j are marked with @pytest.mark.neo4j and are skipped when
the database is not reachable.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraph.core.graph.connection import (
    Neo4jConfig,
    close_driver,
    create_driver,
    load_config,
    verify_connectivity,
)
from codegraph.core.graph.database import DatabaseManager

def _get_test_config() -> Neo4jConfig:
    """Return Neo4j config, preferring env vars, then root config, then defaults."""
    # Standard load_config handles env vars + file fallback
    root_config = Path(__file__).resolve().parents[1] / "config.yaml"
    try:
        return load_config(root_config)
    except ValueError:
        # Fallback if no config file AND no env vars
        return Neo4jConfig(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",
            database="neo4j",
        )

@pytest.fixture(autouse=True)
def reset_database_manager():
    """Reset DatabaseManager singleton before each test."""
    DatabaseManager._instance = None
    yield

@pytest.fixture
def mock_driver():
    """Returns a mocked Neo4j driver."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver

# ---------------------------------------------------------------------------
# Neo4j availability check
# ---------------------------------------------------------------------------

def _neo4j_available() -> bool:
    """Return True if the test Neo4j instance is reachable."""
    try:
        config = _get_test_config()
        driver = create_driver(config)
        ok = verify_connectivity(driver)
        close_driver(driver)
        return ok
    except Exception:
        return False


_NEO4J_AVAILABLE = _neo4j_available()

neo4j_required = pytest.mark.skipif(
    not _NEO4J_AVAILABLE,
    reason="Neo4j not reachable (checked env vars and config.yaml)",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def neo4j_config() -> Neo4jConfig:
    """Return the Neo4j config."""
    return _get_test_config()


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
