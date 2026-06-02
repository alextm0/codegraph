"""Unit tests for query command output modes."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from codegraph.cli.commands.query import query_helper


def test_query_trace_emits_json_only(capsys) -> None:
    """--trace must not print Rich tables or headers."""
    mock_core = MagicMock()
    mock_core.seeds.seeds = {1: 0.5}
    mock_core.seeds.metadata = {1: {"source": "bm25", "qname": "a.py::f"}}

    with (
        patch("codegraph.cli.commands.query.get_database_manager") as db_mgr,
        patch("codegraph.cli.commands.query.load_full_config", return_value={"ppr": {}, "mcp": {}, "seed_selection": {}}),
        patch("codegraph.cli.commands.query.resolve_project_root", return_value=MagicMock()),
        patch("codegraph.core.graph.ppr.create_gds_client", return_value=MagicMock()),
        patch("codegraph.core.retrieval.pipeline.run_core_retrieval", return_value=mock_core),
        patch(
            "codegraph.core.retrieval.trace.build_retrieval_trace",
            return_value={
                "task": "test task",
                "ppr_config": {"damping_factor": 0.7},
                "seeds": [],
                "top_results": [],
            },
        ),
    ):
        db = MagicMock()
        db.is_connected.return_value = True
        db.get_driver.return_value = MagicMock()
        db_mgr.return_value = db

        query_helper(
            MagicMock(),
            "test task",
            None,
            None,
            0,
            0,
            trace=True,
        )

    captured = capsys.readouterr()
    assert "Running retrieval" not in captured.out
    assert "Found" not in captured.out
    payload = json.loads(captured.out)
    assert payload["task"] == "test task"


def test_query_trace_no_results_emits_error_json(capsys) -> None:
    """--trace with no core result returns structured JSON error."""
    with (
        patch("codegraph.cli.commands.query.get_database_manager") as db_mgr,
        patch("codegraph.cli.commands.query.load_full_config", return_value={"ppr": {}, "mcp": {}, "seed_selection": {}}),
        patch("codegraph.cli.commands.query.resolve_project_root", return_value=MagicMock()),
        patch("codegraph.core.graph.ppr.create_gds_client", return_value=MagicMock()),
        patch("codegraph.core.retrieval.pipeline.run_core_retrieval", return_value=None),
    ):
        db = MagicMock()
        db.is_connected.return_value = True
        db.get_driver.return_value = MagicMock()
        db_mgr.return_value = db

        query_helper(MagicMock(), "empty task", None, None, 0, 0, trace=True)

    captured = capsys.readouterr()
    assert "Running retrieval" not in captured.out
    payload = json.loads(captured.out)
    assert payload["task"] == "empty task"
    assert "error" in payload
