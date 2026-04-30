from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

from codegraph.watcher.incremental import update_file_in_graph


def _make_driver():
    return MagicMock()


class TestUpdateFileInGraph:
    def test_existing_file_calls_delete_parse_build(self, tmp_path):
        py_file = tmp_path / "auth.py"
        py_file.write_text("def login(): pass\n")

        mock_driver = _make_driver()
        mock_entities = MagicMock()
        mock_counts = {"File": 1, "Function": 1}

        with (
            patch("codegraph.watcher.incremental.delete_file_entities", return_value=3) as mock_delete,
            patch("codegraph.watcher.incremental.create_parser") as mock_create_parser,
            patch("codegraph.watcher.incremental.parse_file", return_value=mock_entities) as mock_parse,
            patch("codegraph.watcher.incremental.build_graph", return_value=mock_counts) as mock_build,
        ):
            result = update_file_in_graph(mock_driver, str(tmp_path), str(py_file))

        mock_delete.assert_called_once()
        mock_create_parser.assert_called_once()
        mock_parse.assert_called_once()
        mock_build.assert_called_once_with(mock_driver, [mock_entities])

        assert result["deleted"] == 3
        assert result["counts"] == mock_counts

    def test_deleted_file_returns_without_building(self, tmp_path):
        # File does NOT exist
        py_file = tmp_path / "gone.py"

        mock_driver = _make_driver()

        with (
            patch("codegraph.watcher.incremental.delete_file_entities", return_value=2) as mock_delete,
            patch("codegraph.watcher.incremental.create_parser") as mock_create_parser,
            patch("codegraph.watcher.incremental.build_graph") as mock_build,
        ):
            result = update_file_in_graph(mock_driver, str(tmp_path), str(py_file))

        mock_delete.assert_called_once()
        mock_create_parser.assert_not_called()  # parser is created after the existence check
        mock_build.assert_not_called()

        assert result["deleted"] == 2
        assert result["created"] == 0

    def test_parse_error_returns_error_dict(self, tmp_path):
        py_file = tmp_path / "bad.py"
        py_file.write_bytes(b"\xff\xfe broken bytes")

        mock_driver = _make_driver()

        with (
            patch("codegraph.watcher.incremental.delete_file_entities", return_value=1),
            patch("codegraph.watcher.incremental.create_parser"),
            patch("codegraph.watcher.incremental.parse_file", side_effect=ValueError("parse error")),
            patch("codegraph.watcher.incremental.build_graph") as mock_build,
        ):
            result = update_file_in_graph(mock_driver, str(tmp_path), str(py_file))

        mock_build.assert_not_called()
        assert result["deleted"] == 1
        assert "error" in result
        assert "parse error" in result["error"]

    def test_relative_path_resolved_to_absolute(self, tmp_path):
        py_file = tmp_path / "src" / "auth.py"
        py_file.parent.mkdir()
        py_file.write_text("x = 1\n")

        mock_driver = _make_driver()
        mock_entities = MagicMock()

        with (
            patch("codegraph.watcher.incremental.delete_file_entities", return_value=0),
            patch("codegraph.watcher.incremental.create_parser"),
            patch("codegraph.watcher.incremental.parse_file", return_value=mock_entities),
            patch("codegraph.watcher.incremental.build_graph", return_value={}),
        ):
            # Pass relative path string
            result = update_file_in_graph(mock_driver, str(tmp_path), "src/auth.py")

        assert "error" not in result
