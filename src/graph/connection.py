"""Neo4j driver lifecycle: create, verify, and close."""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml
from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Neo4jConfig:
    """Connection parameters for Neo4j."""

    uri: str
    username: str
    password: str
    database: str


def load_config(config_path: str | Path) -> Neo4jConfig:
    """Load Neo4j connection config from a YAML file."""
    with open(config_path) as f:
        data = yaml.safe_load(f)

    neo4j = data["neo4j"]
    return Neo4jConfig(
        uri=neo4j["uri"],
        username=neo4j["username"],
        password=neo4j["password"],
        database=neo4j["database"],
    )


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
