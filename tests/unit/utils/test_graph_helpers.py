"""Unit tests for graph_helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from codegraph.utils.graph_helpers import verify_graph_project_root


def test_verify_graph_project_root_empty_graph(tmp_path) -> None:
    driver = MagicMock()
    session = MagicMock()
    session.run.return_value.single.return_value = None
    driver.session.return_value.__enter__.return_value = session

    ok, msg = verify_graph_project_root(driver, tmp_path)
    assert ok is True
    assert msg == "Graph is empty"


def test_verify_graph_project_root_file_exists(tmp_path) -> None:
    sample = tmp_path / "src" / "app.py"
    sample.parent.mkdir(parents=True)
    sample.write_text("x = 1\n")

    driver = MagicMock()
    session = MagicMock()
    session.run.return_value.single.return_value = {"fp": "src/app.py"}
    driver.session.return_value.__enter__.return_value = session

    ok, msg = verify_graph_project_root(driver, tmp_path)
    assert ok is True
    assert msg == "src/app.py"


def test_verify_graph_project_root_file_missing(tmp_path) -> None:
    driver = MagicMock()
    session = MagicMock()
    session.run.return_value.single.return_value = {"fp": "missing.py"}
    driver.session.return_value.__enter__.return_value = session

    ok, msg = verify_graph_project_root(driver, tmp_path)
    assert ok is False
    assert msg == "missing.py"
