"""Neo4j driver lifecycle: create, verify, and close."""

import logging
from dataclasses import dataclass

from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Neo4jConfig:
    """Connection parameters for Neo4j."""

    uri: str = "neo4j://localhost:7687"
    username: str = "neo4j"
    password: str = "alex17toma02mihai04"
    database: str = "neo4j"


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
