"""Tests for src/graph/connection.py — Neo4j driver lifecycle."""

from pathlib import Path

import pytest

from src.graph.connection import load_config, Neo4jConfig, create_driver, verify_connectivity, close_driver
from tests.conftest import neo4j_required

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# ---------------------------------------------------------------------------
# Neo4jConfig
# ---------------------------------------------------------------------------

def test_load_config_reads_yaml():
    """load_config returns a Neo4jConfig with values from config.yaml."""
    config = load_config(_CONFIG_PATH)
    assert "localhost" in config.uri
    assert "7687" in config.uri
    assert config.username == "neo4j"
    assert config.database == "neo4j"


def test_neo4j_config_is_frozen():
    """Neo4jConfig must be immutable."""
    config = load_config(_CONFIG_PATH)
    with pytest.raises((AttributeError, TypeError)):
        config.uri = "bolt://other:7687"  # type: ignore[misc]


def test_neo4j_config_custom_values():
    """Custom values are stored correctly."""
    config = Neo4jConfig(uri="bolt://remote:7687", username="admin", password="secret", database="mydb")
    assert config.uri == "bolt://remote:7687"
    assert config.username == "admin"
    assert config.password == "secret"
    assert config.database == "mydb"


# ---------------------------------------------------------------------------
# create_driver
# ---------------------------------------------------------------------------

def test_create_driver_returns_driver_object():
    """create_driver returns a Neo4j Driver without raising."""
    config = load_config(_CONFIG_PATH)
    driver = create_driver(config)
    assert driver is not None
    close_driver(driver)


# ---------------------------------------------------------------------------
# verify_connectivity (requires running Neo4j)
# ---------------------------------------------------------------------------

@neo4j_required
def test_verify_connectivity_returns_true_when_reachable(neo4j_driver):
    """verify_connectivity must return True when Neo4j is running."""
    assert verify_connectivity(neo4j_driver) is True


def test_verify_connectivity_returns_false_for_bad_uri():
    """verify_connectivity must return False when the URI is unreachable."""
    base = load_config(_CONFIG_PATH)
    config = Neo4jConfig(uri="bolt://localhost:19999", username=base.username, password=base.password, database=base.database)
    driver = create_driver(config)
    result = verify_connectivity(driver)
    close_driver(driver)
    assert result is False


# ---------------------------------------------------------------------------
# close_driver
# ---------------------------------------------------------------------------

@neo4j_required
def test_close_driver_does_not_raise(neo4j_driver):
    """Closing a second driver (not the session fixture) should not raise."""
    config = load_config(_CONFIG_PATH)
    driver = create_driver(config)
    # Should complete without error
    close_driver(driver)
