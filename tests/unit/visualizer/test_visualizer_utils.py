"""Consolidated unit tests for visualizer backend and frontend utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from codegraph.visualizer.file_source import resolve_source_file
from codegraph.visualizer.graph_filter import (
    config_exclude_patterns,
    filter_graph_for_visualizer,
    is_visualizer_excluded,
)


# ---------------------------------------------------------------------------
# File path resolution (backend)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Graph filtering (backend)
# ---------------------------------------------------------------------------

def test_is_visualizer_excluded_fixture_paths() -> None:
    assert is_visualizer_excluded("tests/fixtures/flask/src/flask/app.py") is True
    assert is_visualizer_excluded("src/codegraph/mcp/server.py") is False


def test_is_visualizer_excluded_codegraph_cache() -> None:
    assert is_visualizer_excluded(
        ".codegraph_cache/repos/django/django/db/models.py"
    ) is True


def test_is_visualizer_excluded_internal_paths() -> None:
    assert is_visualizer_excluded(".gemini/skills/foo/SKILL.md") is True
    assert is_visualizer_excluded("thesis/scripts/build.py") is True
    assert is_visualizer_excluded("projects/flask/src/flask/app.py") is True
    assert is_visualizer_excluded("frontend/src/App.tsx") is False


def test_config_exclude_patterns_merges_parser_and_top_level() -> None:
    cfg = {
        "parser": {"exclude_patterns": ["custom/"]},
        "exclude_patterns": [".venv"],
    }
    patterns = config_exclude_patterns(cfg)
    assert "custom/" in patterns
    assert ".venv" in patterns


def test_is_visualizer_excluded_uses_config_patterns() -> None:
    cfg = {"exclude_patterns": ["scratch/"]}
    assert is_visualizer_excluded("scratch/temp.py", config_exclude_patterns(cfg)) is True


def test_filter_graph_for_visualizer_removes_nodes_and_edges() -> None:
    graph = {
        "nodes": [
            {"id": "src/app.py", "file_path": "src/app.py"},
            {
                "id": "tests/fixtures/flask/app.py",
                "file_path": "tests/fixtures/flask/app.py",
            },
        ],
        "edges": [
            {"source": "src/app.py", "target": "tests/fixtures/flask/app.py", "type": "IMPORTS"},
            {"source": "src/app.py", "target": "src/app.py", "type": "CONTAINS"},
        ],
    }

    filtered = filter_graph_for_visualizer(graph)

    assert len(filtered["nodes"]) == 1
    assert filtered["nodes"][0]["id"] == "src/app.py"
    assert len(filtered["edges"]) == 1
    assert filtered["edges"][0]["type"] == "CONTAINS"


def test_filter_graph_for_visualizer_drops_fixture_paths_v2():
    graph = {
        "nodes": [
            {"id": "src/main.py::main", "file_path": "src/main.py", "name": "main"},
            {"id": "tests/fixtures/x.py::f", "file_path": "tests/fixtures/x.py", "name": "f"},
        ],
        "edges": [
            {
                "source": "src/main.py::main",
                "target": "tests/fixtures/x.py::f",
                "type": "CALLS",
            },
        ],
    }
    filtered = filter_graph_for_visualizer(graph)
    assert len(filtered["nodes"]) == 1
    assert filtered["nodes"][0]["file_path"] == "src/main.py"
    assert filtered["edges"] == []


# ---------------------------------------------------------------------------
# Frontend utility presence checks
# ---------------------------------------------------------------------------

def test_build_file_tree_module_exports():
    root = Path(__file__).resolve().parents[3]
    src = (root / "frontend" / "src" / "utils" / "buildFileTree.ts").read_text(
        encoding="utf-8"
    )
    assert "export function buildFileTree" in src
    assert "export function filterFileTree" in src
    assert "export function expandPathsForFilter" in src
