"""Shared utilities for CLI command helpers."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich.console import Console

from codegraph.core.graph import get_database_manager
from codegraph.utils.config import load_raw_config, resolve_project_root

logger = logging.getLogger(__name__)
console = Console()

_TIMESTAMP_FILE_NAME = ".codegraph_last_built"


def _initialize_db(config_path: Path):
    """Initialize the database manager with the given config."""
    db_manager = get_database_manager()
    db_manager.initialize(str(config_path))
    return db_manager


def _write_build_timestamp(config_path: Path) -> None:
    """Write current UTC timestamp next to config.yaml after a successful rebuild."""
    import datetime

    ts_file = config_path.parent / _TIMESTAMP_FILE_NAME
    ts_file.write_text(
        datetime.datetime.now(datetime.UTC).isoformat(), encoding="utf-8"
    )


def _read_build_timestamp(config_path: Path) -> str | None:
    """Return ISO timestamp string of last rebuild, or None if not found."""
    ts_file = config_path.parent / _TIMESTAMP_FILE_NAME
    if ts_file.exists():
        return ts_file.read_text(encoding="utf-8").strip()
    return None
