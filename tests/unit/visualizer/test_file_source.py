"""Unit tests for visualizer file path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from codegraph.visualizer.file_source import resolve_source_file


def test_resolve_source_file_finds_file(tmp_path: Path) -> None:
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    target = src / "module.py"
    target.write_text("x = 1\n", encoding="utf-8")

    resolved = resolve_source_file(str(tmp_path), "src/pkg/module.py")
    assert resolved == target.resolve()


def test_resolve_source_file_strips_leading_dot_slash(tmp_path: Path) -> None:
    f = tmp_path / "foo.py"
    f.write_text("pass\n", encoding="utf-8")
    assert resolve_source_file(str(tmp_path), "./foo.py") == f.resolve()


def test_resolve_source_file_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_source_file(str(tmp_path), "missing.py")
