"""Resolve project-relative file paths for the visualizer file API."""

from __future__ import annotations

from pathlib import Path

from codegraph.core.graph.utils import normalize_path


def resolve_source_file(project_root: str, file_path: str) -> Path:
    """Return an on-disk path for a graph file_path, trying common variants."""
    root = Path(project_root).resolve()
    rel = normalize_path(file_path.strip()).lstrip("./")

    candidates = [
        root / rel,
        root / file_path.strip(),
    ]
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not str(resolved).startswith(str(root)):
            continue
        if resolved.is_file():
            return resolved

    raise FileNotFoundError(rel)
