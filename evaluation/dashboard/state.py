"""SQLite persistence layer for evaluation dashboard."""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from pathlib import Path

from evaluation.dashboard.config import normalize_and_validate_config
from evaluation.dashboard.models import RunConfig, RunRecord

_MIGRATION_COLUMNS: dict[str, str] = {
    "last_error_summary": "TEXT",
    "last_command": "TEXT",
}


def get_db_path() -> Path:
    """Return absolute path to runs.db (evaluation/dashboard/runs.db relative to project root).

    Project root = parent of parent of this file's directory
    i.e. Path(__file__).parent.parent.parent
    """
    project_root = Path(__file__).parent.parent.parent
    return project_root / "evaluation" / "dashboard" / "runs.db"


def init_db(db_path: Path) -> None:
    """Create DB and runs table if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                output_dir TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                config_json TEXT,
                pid INTEGER,
                exit_code INTEGER,
                last_error_summary TEXT,
                last_command TEXT
            )
            """
        )
        _ensure_schema(conn)
        conn.commit()
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Add newly introduced columns when opening older DB files."""
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(runs)")
    }
    for column_name, column_type in _MIGRATION_COLUMNS.items():
        if column_name not in columns:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {column_name} {column_type}")


def upsert_run(record: RunRecord, db_path: Path | None = None) -> None:
    """Insert or replace a run record. Serializes config to JSON."""
    if db_path is None:
        db_path = get_db_path()

    init_db(db_path)

    config_json = None
    if record.config is not None:
        config_json = json.dumps(dataclasses.asdict(record.config))

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs
            (id, output_dir, status, started_at, finished_at, config_json, pid, exit_code, last_error_summary, last_command)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.output_dir,
                record.status,
                record.started_at,
                record.finished_at,
                config_json,
                record.pid,
                record.exit_code,
                record.last_error_summary,
                record.last_command,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_run(run_id: str, db_path: Path | None = None) -> RunRecord | None:
    """Fetch single run by id. Returns None if not found."""
    if db_path is None:
        db_path = get_db_path()

    if not db_path.exists():
        return None
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT id, output_dir, status, started_at, finished_at, config_json, pid, exit_code, last_error_summary, last_command
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        config = None
        if row["config_json"] is not None:
            try:
                config_dict = json.loads(row["config_json"])
                config = RunConfig(**config_dict)
            except (json.JSONDecodeError, TypeError):
                config = None

        return RunRecord(
            id=row["id"],
            output_dir=row["output_dir"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            config=config,
            pid=row["pid"],
            exit_code=row["exit_code"],
            last_error_summary=row["last_error_summary"],
            last_command=row["last_command"],
        )
    finally:
        conn.close()


def list_runs(db_path: Path | None = None) -> list[RunRecord]:
    """Return all runs, ordered by started_at DESC."""
    if db_path is None:
        db_path = get_db_path()

    if not db_path.exists():
        return []
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT id, output_dir, status, started_at, finished_at, config_json, pid, exit_code, last_error_summary, last_command
            FROM runs
            ORDER BY started_at DESC NULLS LAST
            """
        )
        rows = cursor.fetchall()

        runs = []
        for row in rows:
            config = None
            if row["config_json"] is not None:
                try:
                    config_dict = json.loads(row["config_json"])
                    config = RunConfig(**config_dict)
                except (json.JSONDecodeError, TypeError):
                    config = None

            runs.append(
                RunRecord(
                    id=row["id"],
                    output_dir=row["output_dir"],
                    status=row["status"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    config=config,
                    pid=row["pid"],
                    exit_code=row["exit_code"],
                    last_error_summary=row["last_error_summary"],
                    last_command=row["last_command"],
                )
            )

        return runs
    finally:
        conn.close()


def discover_existing_runs(results_root: Path, db_path: Path | None = None) -> int:
    """
    Scan results_root for subdirectories containing summary.json or per_instance.jsonl.
    For each found directory NOT already in the DB, insert a RunRecord with:
      - id = directory name (e.g. "pilot_001")
      - output_dir = str(directory absolute path)
      - status = "completed" if summary.json exists, else "stopped"
      - started_at = None (unknown)
      - config = None (read from summary.json if ablation/retriever fields present)
    Returns count of newly discovered runs.
    """
    if db_path is None:
        db_path = get_db_path()

    init_db(db_path)

    # Get all existing run IDs in DB
    existing_ids = {run.id for run in list_runs(db_path)}

    # Scan immediate subdirectories
    discovered_count = 0
    if not results_root.exists():
        return discovered_count

    for subdir in results_root.iterdir():
        if not subdir.is_dir():
            continue

        run_id = subdir.name

        # Skip if already in DB
        if run_id in existing_ids:
            continue

        # Check if directory contains per_instance.jsonl or summary.json
        per_instance_file = subdir / "per_instance.jsonl"
        summary_file = subdir / "summary.json"

        if not per_instance_file.exists() and not summary_file.exists():
            continue

        # Determine status and extract config if possible
        status = "stopped"
        config = None

        if summary_file.exists():
            status = "completed"
            try:
                with open(summary_file) as f:
                    summary_data = json.load(f)

                # Try to extract config from summary.json
                config_dict = {
                    "output_dir": str(subdir.absolute()),
                    "retriever": summary_data.get("retriever", ""),
                    "ablation": summary_data.get("ablation", ""),
                    "grouping": summary_data.get("grouping", ""),
                    "limit": summary_data.get("limit", 0),
                    "config_path": summary_data.get("config_path", ""),
                    "cache_dir": summary_data.get("cache_dir", ""),
                    "retry_errors": summary_data.get("retry_errors", False),
                }
                raw_config = RunConfig(**config_dict)
                checked = normalize_and_validate_config(raw_config)
                config = checked.config
            except (json.JSONDecodeError, TypeError, KeyError):
                # If we can't parse or reconstruct config, leave it as None
                pass

        # Create and insert run record
        record = RunRecord(
            id=run_id,
            output_dir=str(subdir.absolute()),
            status=status,
            started_at=None,
            finished_at=None,
            config=config,
            pid=None,
            exit_code=None,
        )
        upsert_run(record, db_path)
        discovered_count += 1

    return discovered_count
