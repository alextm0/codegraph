"""Unit tests for visualizer API models and doctor checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codegraph.cli.commands.doctor import run_doctor_checks
from codegraph.visualizer.models import (
    FileSourceResponse,
    PathBetweenResponse,
    QueryRequest,
    StatsResponse,
)


def test_query_request_defaults():
    req = QueryRequest(task="fix auth bug")
    assert req.top_k == 10
    assert req.mentioned_entities is None
    assert req.token_budget == 0


def test_query_request_extended_fields():
    req = QueryRequest(
        task="task",
        top_k=15,
        mentioned_entities=["AuthService"],
        token_budget=4000,
    )
    assert req.mentioned_entities == ["AuthService"]
    assert req.token_budget == 4000


def test_file_source_response_shape():
    resp = FileSourceResponse(
        file_path="src/foo.py",
        content="x = 1\n",
        line_count=1,
        entities=[],
    )
    assert resp.file_path == "src/foo.py"
    assert resp.line_count == 1


def test_path_between_response_shape():
    resp = PathBetweenResponse(
        source="a::x",
        target="b::y",
        linked=True,
        path_ids=["a::x", "b::y"],
        hops=1,
    )
    assert resp.linked is True
    assert resp.hops == 1


def test_stats_response_optional_fields():
    resp = StatsResponse(
        nodes={"Function": 10},
        edges={"CALLS": 5},
        most_connected_files=[{"entity_count": 3, "file_path": "a.py"}],
        last_build="2026-01-01T00:00:00",
    )
    assert resp.last_build.startswith("2026")
    assert resp.most_connected_files[0]["file_path"] == "a.py"


@patch("codegraph.cli.commands.doctor.get_database_manager")
def test_run_doctor_checks_missing_config(mock_db: MagicMock, tmp_path: Path):
    missing = tmp_path / "missing.yaml"
    manager = MagicMock()
    manager.is_connected.return_value = False
    manager._config = None
    mock_db.return_value = manager

    result = run_doctor_checks(missing)
    assert result["ok"] is False
    assert any(c["name"] == "config_file" and not c["ok"] for c in result["checks"])


@patch("codegraph.cli.commands.doctor.get_database_manager")
def test_run_doctor_checks_tree_sitter_ok(mock_db: MagicMock, tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text("project_root: .\nneo4j:\n  password: test\n", encoding="utf-8")

    manager = MagicMock()
    manager.is_connected.return_value = False
    manager._config = MagicMock(uri="neo4j://localhost:7687")
    mock_db.return_value = manager

    with patch.dict("os.environ", {"NEO4J_PASSWORD": "secret"}):
        result = run_doctor_checks(config)

    names = [c["name"] for c in result["checks"]]
    assert "config_file" in names
    assert "tree_sitter" in names
    assert any(c["name"] == "tree_sitter" and c["ok"] for c in result["checks"])
