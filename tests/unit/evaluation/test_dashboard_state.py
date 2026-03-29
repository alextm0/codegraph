"""Unit tests for evaluation/dashboard/state.py."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from evaluation.dashboard.models import RunConfig, RunRecord
from evaluation.dashboard.state import (
    get_run,
    init_db,
    list_runs,
    upsert_run,
)


def _make_record(run_id: str = "run_001", **kwargs) -> RunRecord:
    defaults = {
        "id": run_id,
        "output_dir": f"/tmp/{run_id}",
        "status": "running",
        "started_at": "2026-03-14T10:00:00",
    }
    defaults.update(kwargs)
    return RunRecord(**defaults)


def _make_config(**kwargs) -> RunConfig:
    defaults = {
        "output_dir": "/tmp/run_001",
        "retriever": "ppr",
        "ablation": "baseline",
        "grouping": "repo_commit",
        "limit": 5,
        "config_path": "config.yaml",
        "cache_dir": ".codegraph_cache/repos",
    }
    defaults.update(kwargs)
    return RunConfig(**defaults)


# ──────────────────────── init_db / schema ──────────────────────────────────

def test_init_db_creates_table(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "runs" in tables


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    init_db(db_path)  # should not raise


def test_schema_migration_adds_missing_columns(tmp_path: Path) -> None:
    """Opening a DB missing last_error_summary / last_command should add those columns."""
    db_path = tmp_path / "old.db"
    # Create a minimal DB without the new columns
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            output_dir TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            config_json TEXT,
            pid INTEGER,
            exit_code INTEGER
        )
        """
    )
    conn.commit()
    conn.close()

    # init_db should migrate it without raising
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    conn.close()
    assert "last_error_summary" in columns
    assert "last_command" in columns


# ──────────────────────── upsert_run / get_run round-trip ───────────────────

def test_upsert_and_get_run_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    record = _make_record(
        run_id="run_001",
        status="running",
        started_at="2026-03-14T10:00:00",
        exit_code=None,
        last_error_summary=None,
        last_command="python -m evaluation.swe_bench_runner --output /tmp/run_001",
        config=_make_config(),
    )
    upsert_run(record, db_path=db_path)
    fetched = get_run("run_001", db_path=db_path)

    assert fetched is not None
    assert fetched.id == "run_001"
    assert fetched.status == "running"
    assert fetched.last_command == record.last_command
    assert fetched.last_error_summary is None


def test_diagnostic_fields_persisted(tmp_path: Path) -> None:
    """last_error_summary and last_command survive a DB round-trip."""
    db_path = tmp_path / "test.db"
    record = _make_record(
        run_id="run_fail",
        status="failed",
        exit_code=2,
        last_error_summary="exit=2: error: argument --retriever: invalid choice: ''",
        last_command="python -m evaluation.swe_bench_runner --retriever ''",
    )
    upsert_run(record, db_path=db_path)
    fetched = get_run("run_fail", db_path=db_path)

    assert fetched is not None
    assert fetched.exit_code == 2
    assert fetched.last_error_summary == record.last_error_summary
    assert fetched.last_command == record.last_command


def test_upsert_replaces_existing_record(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    record = _make_record("run_x", status="running")
    upsert_run(record, db_path=db_path)

    record.status = "completed"
    record.exit_code = 0
    record.finished_at = "2026-03-14T11:00:00"
    upsert_run(record, db_path=db_path)

    fetched = get_run("run_x", db_path=db_path)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.exit_code == 0


def test_get_run_missing_returns_none(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    assert get_run("nonexistent", db_path=db_path) is None


def test_get_run_no_db_file_returns_none(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    assert get_run("any", db_path=db_path) is None


# ──────────────────────── config serialization ──────────────────────────────

def test_config_survives_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    cfg = _make_config(retriever="bm25", ablation="no_idf", limit=20)
    record = _make_record("run_cfg", config=cfg)
    upsert_run(record, db_path=db_path)

    fetched = get_run("run_cfg", db_path=db_path)
    assert fetched is not None
    assert fetched.config is not None
    assert fetched.config.retriever == "bm25"
    assert fetched.config.ablation == "no_idf"
    assert fetched.config.limit == 20


def test_record_without_config_stored_cleanly(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    record = _make_record("run_no_cfg", config=None)
    upsert_run(record, db_path=db_path)

    fetched = get_run("run_no_cfg", db_path=db_path)
    assert fetched is not None
    assert fetched.config is None


# ──────────────────────── list_runs ordering ────────────────────────────────

def test_list_runs_ordered_by_started_at_desc(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    upsert_run(_make_record("run_a", started_at="2026-03-14T08:00:00"), db_path=db_path)
    upsert_run(_make_record("run_b", started_at="2026-03-14T10:00:00"), db_path=db_path)
    upsert_run(_make_record("run_c", started_at="2026-03-14T09:00:00"), db_path=db_path)

    runs = list_runs(db_path=db_path)
    ids = [r.id for r in runs]
    assert ids == ["run_b", "run_c", "run_a"]


def test_list_runs_empty_db(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    assert list_runs(db_path=db_path) == []


def test_list_runs_no_db_file(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    assert list_runs(db_path=db_path) == []
