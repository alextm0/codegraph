import unittest
from unittest.mock import MagicMock, patch
from codegraph.core.graph.database import DatabaseManager, get_database_manager

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        # Reset singleton instance between tests
        DatabaseManager._instance = None

    def test_singleton_pattern(self):
        """DatabaseManager should return the same instance."""
        dm1 = get_database_manager()
        dm2 = get_database_manager()
        self.assertIs(dm1, dm2)

    @patch("codegraph.core.graph.database.GraphDatabase.driver")
    @patch("codegraph.core.graph.database.load_config")
    def test_get_driver_singleton(self, mock_load_config, mock_driver_factory):
        """get_driver should return the same driver instance."""
        mock_config = MagicMock()
        mock_config.uri = "bolt://localhost:7687"
        mock_config.username = "neo4j"
        mock_config.password = "password"
        mock_load_config.return_value = mock_config
        
        mock_driver = MagicMock()
        mock_driver_factory.return_value = mock_driver

        dm = get_database_manager()
        dm.initialize("dummy_config.yaml")
        
        driver1 = dm.get_driver()
        driver2 = dm.get_driver()
        
        self.assertIs(driver1, driver2)
        mock_driver_factory.assert_called_once()

    def test_close_driver(self):
        """close_driver should close the driver and reset it."""
        dm = get_database_manager()
        mock_driver = MagicMock()
        dm._driver = mock_driver
        
        dm.close_driver()
        
        mock_driver.close.assert_called_once()
        self.assertIsNone(dm._driver)

    @patch("codegraph.core.graph.database.GraphDatabase.driver")
    @patch("codegraph.core.graph.database.load_config")
    def test_is_connected(self, mock_load_config, mock_driver_factory):
        """is_connected should call verify_connectivity."""
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        
        mock_driver = MagicMock()
        mock_driver_factory.return_value = mock_driver
        
        dm = get_database_manager()
        dm.initialize("dummy_config.yaml")
        
        result = dm.is_connected()
        
        self.assertTrue(result)
        mock_driver.verify_connectivity.assert_called_once()

    @patch("codegraph.core.graph.database.GraphDatabase.driver")
    @patch("codegraph.core.graph.database.load_config")
    def test_is_connected_failure(self, mock_load_config, mock_driver_factory):
        """is_connected should return False if verify_connectivity fails."""
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        
        mock_driver = MagicMock()
        mock_driver.verify_connectivity.side_effect = Exception("Connection failed")
        mock_driver_factory.return_value = mock_driver
        
        dm = get_database_manager()
        dm.initialize("dummy_config.yaml")
        
        result = dm.is_connected()
        
        self.assertFalse(result)
