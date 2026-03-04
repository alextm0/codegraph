import logging
import threading
from typing import Optional

from neo4j import GraphDatabase, Driver

from codegraph.core.graph.connection import load_config, Neo4jConfig

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Thread-safe singleton to manage Neo4j driver and connection pool."""

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
                    cls._instance._driver = None
                    cls._instance._driver_lock = threading.Lock()
                    cls._instance._config = None
        return cls._instance

    def initialize(self, config_path: str):
        """Initialize the manager with a configuration path."""
        with self._driver_lock:
            self._config = load_config(config_path)
            if self._driver:
                self._driver.close()
                self._driver = None

    def get_driver(self) -> Driver:
        """Get or create the Neo4j driver instance."""
        if self._config is None:
            # Fallback to default config if not initialized
            from pathlib import Path
            config_path = Path("config.yaml")
            self.initialize(str(config_path))

        if self._driver is None:
            with self._driver_lock:
                if self._driver is None:
                    try:
                        self._driver = GraphDatabase.driver(
                            self._config.uri,
                            auth=(self._config.username, self._config.password)
                        )
                        logger.debug("Created Neo4j driver for %s", self._config.uri)
                    except Exception as e:
                        logger.error("Failed to create Neo4j driver: %s", e)
                        raise
        return self._driver

    def close_driver(self):
        """Close the Neo4j driver and release resources."""
        with self._driver_lock:
            if self._driver:
                self._driver.close()
                self._driver = None
                logger.debug("Neo4j driver closed")

    def is_connected(self) -> bool:
        """Check if the driver is connected and responsive."""
        try:
            driver = self.get_driver()
            driver.verify_connectivity()
            return True
        except Exception as e:
            logger.warning("Neo4j connectivity check failed: %s", e)
            return False


def get_database_manager() -> DatabaseManager:
    """Get the singleton DatabaseManager instance."""
    return DatabaseManager()
