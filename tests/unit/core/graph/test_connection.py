"""Tests for src/graph/connection.py — Neo4j driver lifecycle."""

import os
from pathlib import Path
import yaml
import pytest

from codegraph.core.graph.connection import load_config, Neo4jConfig, create_driver, verify_connectivity, close_driver
from tests.conftest import neo4j_required

@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary valid config file for testing load_config."""
    config_data = {
        "neo4j": {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "test_password",
            "database": "neo4j"
        }
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)
    return config_path

# ---------------------------------------------------------------------------
# Neo4jConfig
# ---------------------------------------------------------------------------

def test_load_config_reads_yaml(temp_config_file, monkeypatch):
    """load_config returns a Neo4jConfig with values from config.yaml."""
    # Ensure env vars don't override the YAML during this test
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USERNAME", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    
    config = load_config(temp_config_file)
    assert "localhost" in config.uri
    assert "7687" in config.uri
    assert config.username == "neo4j"
    assert config.database == "neo4j"
    assert config.password == "test_password"


def test_neo4j_config_is_frozen(temp_config_file):
    """Neo4jConfig must be immutable."""
    config = load_config(temp_config_file)
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

def test_create_driver_returns_driver_object(temp_config_file):
    """create_driver returns a Neo4j Driver without raising."""
    config = load_config(temp_config_file)
    # create_driver doesn't actually connect immediately, it just creates the object
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


def test_verify_connectivity_returns_false_for_bad_uri(temp_config_file):
    """verify_connectivity must return False when the URI is unreachable."""
    base = load_config(temp_config_file)
    config = Neo4jConfig(uri="bolt://localhost:19999", username=base.username, password=base.password, database=base.database)
    driver = create_driver(config)
    # This should fail connection because nothing is listening on 19999
    result = verify_connectivity(driver)
    close_driver(driver)
    assert result is False


# ---------------------------------------------------------------------------
# close_driver
# ---------------------------------------------------------------------------

@neo4j_required
def test_close_driver_does_not_raise(neo4j_driver, temp_config_file):
    """Closing a second driver (not the session fixture) should not raise."""
    config = load_config(temp_config_file)
    driver = create_driver(config)
    # Should complete without error
    close_driver(driver)
