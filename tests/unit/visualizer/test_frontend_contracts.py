"""Contract tests for visualizer frontend source files."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend" / "src"


def test_theme_tokens_define_semantic_colors_and_schemes():
    css = (FRONTEND / "styles" / "tokens.css").read_text(encoding="utf-8")
    assert "--danger" in css
    assert "--success" in css
    assert '[data-theme="light"]' in css
    assert "color-scheme: light" in css
    assert "color-scheme: dark" in css
    assert "--radius-sm" in css
    assert "--font-body" in css
    assert "--elev-1" in css


def test_left_rail_uses_tabbed_layout_without_graph_search():
    rail = (FRONTEND / "components" / "layout" / "LeftRail.tsx").read_text(encoding="utf-8")
    assert "GraphSearch" not in rail
    assert "'files'" in rail or "files" in rail
    assert "ProjectTree" in rail


def test_time_formatting_utility_and_usage():
    fmt = (FRONTEND / "utils" / "formatTime.ts").read_text(encoding="utf-8")
    assert "formatTimeHms" in fmt
    assert "formatDateTime" in fmt
    status = (FRONTEND / "components" / "layout" / "StatusBar.tsx").read_text(
        encoding="utf-8"
    )
    stats = (FRONTEND / "components" / "layout" / "StatsPopover.tsx").read_text(
        encoding="utf-8"
    )
    assert "formatDisplayTimestamp" in status
    assert "formatDateTime" in stats


def test_view_mode_banner_for_exiting_query():
    banner = (FRONTEND / "components" / "layout" / "ViewModeBanner.tsx").read_text(
        encoding="utf-8"
    )
    assert "Entire codebase" in banner
    graph = (FRONTEND / "hooks" / "useGraphData.ts").read_text(encoding="utf-8")
    assert "stripQueryAnnotations" in graph
    assert "graphRevision" in graph


def test_right_panel_tabs_include_results_explain_inspector():
    src = (FRONTEND / "components" / "panel" / "RightPanelTabs.tsx").read_text(
        encoding="utf-8"
    )
    assert "'results'" in src
    assert "'explain'" in src
    assert "'inspector'" in src
    assert "'file'" in src


def test_graph_controls_and_project_tree_present():
    assert (FRONTEND / "components" / "graph" / "GraphControls.tsx").is_file()
    assert (FRONTEND / "components" / "layout" / "ProjectTree.tsx").is_file()
    tree_util = (FRONTEND / "utils" / "buildFileTree.ts").read_text(encoding="utf-8")
    assert "buildFileTree" in tree_util


def test_collapsible_rail_hook():
    hook = (FRONTEND / "hooks" / "useCollapsedRail.ts").read_text(encoding="utf-8")
    assert "localStorage" in hook


def test_file_api_uses_files_source_endpoint():
    client = (FRONTEND / "api" / "client.ts").read_text(encoding="utf-8")
    assert "/api/files/source" in client
    assert "file_path" in client


def test_graph_helpers_expand_neighbors():
    helpers = (FRONTEND / "components" / "graph" / "graphHelpers.ts").read_text(
        encoding="utf-8"
    )
    assert "expandWithNeighbors" in helpers
    assert "fileNodeIds" in helpers
    assert "fileFocusNodeIds" in helpers
