"""Unit tests for explain command output modes."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch

from codegraph.cli.commands.explain import explain_helper


def test_explain_trace_emits_json_only(capsys) -> None:
    """--trace must not print Rich tables or headers."""
    mock_core = MagicMock()
    mock_core.seeds.seeds = {1: 0.5}
    mock_core.seeds.metadata = {1: {"source": "bm25", "qname": "a.py::f"}}

    with (
        patch("codegraph.cli.commands.explain._initialize_db") as init_db,
        patch("codegraph.cli.commands.explain.load_raw_config", return_value={"ppr": {}, "seed_selection": {}}),
        patch("codegraph.cli.commands.explain.create_gds_client", return_value=MagicMock()),
        patch("codegraph.cli.commands.explain.run_core_retrieval", return_value=mock_core),
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
        init_db.return_value = db

        explain_helper(MagicMock(), "test task", top_k=3, trace=True)

    captured = capsys.readouterr()
    assert "Seeds" not in captured.out
    assert "Explaining:" not in captured.out
    payload = json.loads(captured.out)
    assert payload["task"] == "test task"


def test_explain_trace_no_seeds_emits_error_json(capsys) -> None:
    """--trace with no seeds returns structured JSON error, not Rich text."""
    with (
        patch("codegraph.cli.commands.explain._initialize_db") as init_db,
        patch("codegraph.cli.commands.explain.load_raw_config", return_value={"ppr": {}, "seed_selection": {}}),
        patch("codegraph.cli.commands.explain.create_gds_client", return_value=MagicMock()),
        patch("codegraph.cli.commands.explain.run_core_retrieval", return_value=None),
    ):
        db = MagicMock()
        db.is_connected.return_value = True
        db.get_driver.return_value = MagicMock()
        init_db.return_value = db

        explain_helper(MagicMock(), "empty task", trace=True)

    captured = capsys.readouterr()
    assert "Explaining:" not in captured.out
    payload = json.loads(captured.out)
    assert payload["task"] == "empty task"
    assert "error" in payload
