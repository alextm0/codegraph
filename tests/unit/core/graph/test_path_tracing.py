import unittest
from unittest.mock import MagicMock
from codegraph.core.graph.queries import trace_path_ids_to_seed

class TestPathTracing(unittest.TestCase):
    def test_trace_path_ids_to_seed_success(self):
        # Setup mock driver and session
        mock_driver = MagicMock()
        mock_session = mock_driver.session.return_value.__enter__.return_value
        
        # Setup mock result
        mock_result = MagicMock()
        mock_result.single.return_value = {
            "path_ids": ["src.main", "src.utils", "target_file.py"]
        }
        mock_session.run.return_value = mock_result
        
        seed_ids = [1, 2]
        file_path = "target_file.py"
        
        # Execute
        path_ids = trace_path_ids_to_seed(mock_driver, seed_ids, file_path)
        
        # Verify
        self.assertEqual(path_ids, ["src.main", "src.utils", "target_file.py"])
        mock_session.run.assert_called()
        
    def test_trace_path_ids_to_seed_no_path(self):
        # Setup mock driver and session
        mock_driver = MagicMock()
        mock_session = mock_driver.session.return_value.__enter__.return_value
        
        # Setup mock result to return None (no record found)
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        
        seed_ids = [1, 2]
        file_path = "target_file.py"
        
        # Execute
        path_ids = trace_path_ids_to_seed(mock_driver, seed_ids, file_path)
        
        # Verify
        self.assertEqual(path_ids, [])

if __name__ == "__main__":
    unittest.main()
