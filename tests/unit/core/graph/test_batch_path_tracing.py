import unittest
from unittest.mock import MagicMock, patch
from codegraph.core.graph.queries import batch_trace_paths

class TestBatchPathTracing(unittest.TestCase):
    def test_batch_trace_paths_success(self):
        mock_driver = MagicMock()
        mock_session = mock_driver.session.return_value.__enter__.return_value
        
        # 1. Mock direct seeds check (returns nothing for this test)
        mock_direct_res = MagicMock()
        mock_direct_res.__iter__.return_value = iter([])
        
        # 2. Mock batch trace query
        mock_query_res = MagicMock()
        mock_query_res.__iter__.return_value = iter([
            {
                "tid": "file1.py",
                "path_ids": ["seed1", "file1.py"],
                "node_names": ["Seed One", "file1.py"],
                "rel_types": ["CONTAINS"]
            },
            {
                "tid": "file2.py",
                "path_ids": ["seed2", "mid", "file2.py"],
                "node_names": ["Seed Two", "Middle", "file2.py"],
                "rel_types": ["CALLS", "CONTAINS"]
            }
        ])
        
        mock_session.run.side_effect = [mock_direct_res, mock_query_res]
        
        seed_ids = [1, 2]
        file_paths = ["file1.py", "file2.py"]
        
        results = batch_trace_paths(mock_driver, seed_ids, file_paths)
        
        self.assertEqual(len(results), 2)
        self.assertIn("file1.py", results)
        self.assertIn("file2.py", results)
        
        self.assertEqual(results["file1.py"]["path_ids"], ["seed1", "file1.py"])
        self.assertIn("Seed One -[CONTAINS]-> file1.py", results["file1.py"]["path_str"])
        
        self.assertEqual(results["file2.py"]["path_ids"], ["seed2", "mid", "file2.py"])
        self.assertIn("Seed Two -[CALLS]-> Middle -[CONTAINS]-> file2.py", results["file2.py"]["path_str"])

    def test_batch_trace_paths_direct_seed(self):
        mock_driver = MagicMock()
        mock_session = mock_driver.session.return_value.__enter__.return_value
        
        # Mock direct seeds check
        mock_direct_res = MagicMock()
        mock_direct_res.__iter__.return_value = iter([{"qname": "file1.py", "fp": "file1.py"}])
        
        # Mock batch trace query (for remaining files)
        mock_query_res = MagicMock()
        mock_query_res.__iter__.return_value = iter([
            {
                "tid": "file2.py",
                "path_ids": ["seed2", "file2.py"],
                "node_names": ["Seed Two", "file2.py"],
                "rel_types": ["CONTAINS"]
            }
        ])
        
        mock_session.run.side_effect = [mock_direct_res, mock_query_res]
        
        seed_ids = [1, 2]
        file_paths = ["file1.py", "file2.py"]
        
        results = batch_trace_paths(mock_driver, seed_ids, file_paths)
        
        self.assertEqual(results["file1.py"]["path_str"], "direct seed")
        self.assertEqual(results["file1.py"]["path_ids"], ["file1.py"])
        
        self.assertEqual(results["file2.py"]["path_ids"], ["seed2", "file2.py"])

    def test_batch_trace_paths_empty(self):
        mock_driver = MagicMock()
        results = batch_trace_paths(mock_driver, [1], [])
        self.assertEqual(results, {})

    def test_batch_trace_paths_error(self):
        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("DB error")
        
        results = batch_trace_paths(mock_driver, [1], ["file1.py"])
        self.assertEqual(results["file1.py"]["path_str"], "(trace error)")

if __name__ == "__main__":
    unittest.main()
