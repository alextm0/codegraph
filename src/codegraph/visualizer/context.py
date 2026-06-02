"""Shared state passed to visualizer route handlers."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neo4j import Driver


@dataclass
class VisualizerContext:
    """Dependencies for API route handlers."""

    driver: Driver
    raw_config: dict[str, Any]
    project_root: str
    config_path: Path | None
    base_dir: Path
    schedule_broadcast: Callable[[dict[str, Any]], None]
    index_lock: threading.Lock = field(default_factory=threading.Lock)
    indexing_in_progress: dict[str, bool] = field(
        default_factory=lambda: {"value": False}
    )
