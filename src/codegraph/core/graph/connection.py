import os
import logging
from dataclasses import dataclass
from pathlib import Path

import yaml
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Neo4jConfig:
    """Connection parameters for Neo4j."""

    uri: str
    username: str
    password: str
    database: str


def load_config(config_path: str | Path) -> Neo4jConfig:
    """Load Neo4j connection config, enforcing URI, username, and password."""
    data = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

    neo4j = data.get("neo4j", {})
    
    uri = os.getenv("NEO4J_URI", neo4j.get("uri"))
    username = os.getenv("NEO4J_USERNAME", neo4j.get("username"))
    password = os.getenv("NEO4J_PASSWORD", neo4j.get("password"))

    if not all([uri, username, password]):
        missing = []
        if not uri: missing.append("NEO4J_URI")
        if not username: missing.append("NEO4J_USERNAME")
        if not password: missing.append("NEO4J_PASSWORD")
        raise ValueError(f"Missing mandatory Neo4j configuration: {', '.join(missing)}")

    return Neo4jConfig(
        uri=uri,
        username=username,
        password=password,
        database="neo4j",
    )


def load_full_config(config_path: str | Path) -> dict:
    """Load and return the entire config.yaml as a plain dictionary.

    Used by the pipeline and MCP server to access all config sections
    (neo4j, ppr, seed_selection, mcp, project_root).
    """
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_driver(config: Neo4jConfig) -> Driver:
    """Create and return a Neo4j driver for the given config."""
    driver = GraphDatabase.driver(config.uri, auth=(config.username, config.password))
    logger.debug("Created Neo4j driver for %s", config.uri)
    return driver


def verify_connectivity(driver: Driver) -> bool:
    """Return True if the driver can reach the database, False otherwise."""
    try:
        driver.verify_connectivity()
        logger.debug("Neo4j connectivity verified")
        return True
    except Exception as exc:
        logger.warning("Neo4j connectivity check failed: %s", exc)
        return False


def close_driver(driver: Driver) -> None:
    """Close the driver and release all connections."""
    driver.close()
    logger.debug("Neo4j driver closed")
