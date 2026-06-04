"""Doctor command helper and structured diagnostics for API use."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from codegraph.core.graph import get_database_manager
from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.logging import setup_logging

from codegraph.cli.commands._shared import console


@dataclass(frozen=True)
class DoctorCheck:
    """Single diagnostic check result."""

    name: str
    ok: bool
    message: str
    fix_hint: str | None = None
    severity: str = "error"  # error | warning | skip


def run_doctor_checks(config_path: Path | None = None) -> dict:
    """Run health checks and return structured JSON-serializable results."""
    checks: list[DoctorCheck] = []
    all_ok = True
    config_ok = False
    raw: dict = {}
    proj_root = Path(".")

    if config_path is None or not config_path.exists():
        checks.append(
            DoctorCheck(
                name="config_file",
                ok=False,
                message=f"config.yaml not found at {config_path or 'unknown'}",
                fix_hint="Run codegraph init to create config.yaml",
            )
        )
        all_ok = False
    else:
        try:
            raw = load_raw_config(config_path)
            config_ok = True
            checks.append(
                DoctorCheck(
                    name="config_file",
                    ok=True,
                    message=f"Config found at {config_path}",
                )
            )
        except Exception as exc:
            checks.append(
                DoctorCheck(
                    name="config_file",
                    ok=False,
                    message=f"Could not read config: {exc}",
                    fix_hint="Fix config.yaml syntax or run codegraph init",
                )
            )
            all_ok = False

        if config_ok:
            proj_root = resolve_project_root(raw, config_path)
            if proj_root.exists():
                checks.append(
                    DoctorCheck(
                        name="project_root",
                        ok=True,
                        message=f"Project root exists: {proj_root}",
                    )
                )
            else:
                checks.append(
                    DoctorCheck(
                        name="project_root",
                        ok=False,
                        message=f"Project root not found: {proj_root}",
                        fix_hint="Update project_root in config.yaml",
                    )
                )
                all_ok = False

            has_password = bool(
                os.getenv("NEO4J_PASSWORD") or raw.get("neo4j", {}).get("password")
            )
            if not has_password:
                checks.append(
                    DoctorCheck(
                        name="neo4j_password",
                        ok=False,
                        message="Neo4j password not set",
                        fix_hint="Set NEO4J_PASSWORD in .env or run codegraph init",
                    )
                )
                all_ok = False
            else:
                checks.append(
                    DoctorCheck(
                        name="neo4j_password",
                        ok=True,
                        message="Neo4j password available",
                    )
                )

    db_manager = get_database_manager()
    connected = False

    try:
        connected = db_manager.is_connected()
        if connected:
            uri = db_manager._config.uri if db_manager._config else "Neo4j"
            checks.append(
                DoctorCheck(
                    name="neo4j_connectivity",
                    ok=True,
                    message=f"Connected to {uri}",
                )
            )
        else:
            uri = (
                db_manager._config.uri
                if db_manager._config
                else "neo4j://localhost:7687"
            )
            checks.append(
                DoctorCheck(
                    name="neo4j_connectivity",
                    ok=False,
                    message=f"Cannot reach Neo4j at {uri}",
                    fix_hint="Start Neo4j (Neo4j Desktop → Start, or: neo4j start)",
                )
            )
            all_ok = False
    except Exception as exc:
        checks.append(
            DoctorCheck(
                name="neo4j_connectivity",
                ok=False,
                message=f"Connection error: {exc}",
                fix_hint="Check Neo4j is running and credentials are correct",
            )
        )
        all_ok = False

    if connected:
        try:
            from codegraph.core.graph.ppr import create_gds_client

            gds = create_gds_client(db_manager.get_driver())
            version = gds.version()
            checks.append(
                DoctorCheck(
                    name="gds_plugin",
                    ok=True,
                    message=f"GDS Plugin installed (version: {version})",
                )
            )
        except Exception as exc:
            checks.append(
                DoctorCheck(
                    name="gds_plugin",
                    ok=False,
                    message=f"GDS check failed: {exc}",
                    fix_hint="Install GDS in Neo4j Desktop → Plugins",
                )
            )
            all_ok = False
    else:
        checks.append(
            DoctorCheck(
                name="gds_plugin",
                ok=False,
                message="Skipped (Neo4j not reachable)",
                severity="skip",
            )
        )

    if connected:
        try:
            from codegraph.core.graph.queries import count_nodes_by_label

            node_counts = count_nodes_by_label(db_manager.get_driver())
            total = sum(node_counts.values())
            if total > 0:
                checks.append(
                    DoctorCheck(
                        name="graph_index",
                        ok=True,
                        message=f"Graph has {total} nodes",
                    )
                )
                if config_ok:
                    from codegraph.utils.graph_helpers import verify_graph_project_root

                    aligned, sample = verify_graph_project_root(
                        db_manager.get_driver(), proj_root
                    )
                    if aligned:
                        checks.append(
                            DoctorCheck(
                                name="graph_project_alignment",
                                ok=True,
                                message="Indexed files resolve under project root",
                            )
                        )
                    else:
                        checks.append(
                            DoctorCheck(
                                name="graph_project_alignment",
                                ok=False,
                                message=f"Graph may be out of sync (sample: {sample})",
                                fix_hint="Run codegraph rebuild after fixing project_root",
                                severity="warning",
                            )
                        )
                        all_ok = False
            else:
                checks.append(
                    DoctorCheck(
                        name="graph_index",
                        ok=False,
                        message="Graph is empty",
                        fix_hint="Run codegraph rebuild to index your project",
                        severity="warning",
                    )
                )
        except Exception as exc:
            checks.append(
                DoctorCheck(
                    name="graph_index",
                    ok=False,
                    message=f"Could not check graph: {exc}",
                    severity="warning",
                )
            )
    else:
        checks.append(
            DoctorCheck(
                name="graph_index",
                ok=False,
                message="Skipped (Neo4j not reachable)",
                severity="skip",
            )
        )

    try:
        from tree_sitter import Language, Parser  # noqa: F401
        import tree_sitter_python  # noqa: F401

        checks.append(
            DoctorCheck(
                name="tree_sitter",
                ok=True,
                message="tree-sitter and python parser available",
            )
        )
    except ImportError as exc:
        checks.append(
            DoctorCheck(
                name="tree_sitter",
                ok=False,
                message=f"tree-sitter check failed: {exc}",
                fix_hint="pip install tree-sitter tree-sitter-python",
            )
        )
        all_ok = False

    return {
        "ok": all_ok,
        "checks": [
            {
                "name": c.name,
                "ok": c.ok,
                "message": c.message,
                "fix_hint": c.fix_hint,
                "severity": c.severity,
            }
            for c in checks
        ],
    }


def doctor_helper(config_path: Path | None = None) -> None:
    """Run health checks on config, Neo4j, GDS, and dependencies."""
    setup_logging(level=logging.WARNING)
    result = run_doctor_checks(config_path)
    ok = result["ok"]

    console.print("[bold cyan]Running CodeGraph Diagnostics...[/bold cyan]\n")

    section = 0
    for check in result["checks"]:
        if check["name"] == "neo4j_connectivity":
            section = 1
            console.print("\n[bold]1. Checking Neo4j Connectivity...[/bold]")
        elif check["name"] == "gds_plugin":
            section = 2
            console.print("\n[bold]2. Checking GDS Plugin...[/bold]")
        elif check["name"] == "graph_index":
            section = 3
            console.print("\n[bold]3. Checking Graph Index...[/bold]")
        elif check["name"] == "tree_sitter":
            section = 4
            console.print("\n[bold]4. Checking Tree-Sitter Installation...[/bold]")
        elif section == 0:
            console.print("[bold]0. Checking Configuration...[/bold]")

        if check["severity"] == "skip":
            console.print(f"   [yellow]![/yellow] {check['message']}")
        elif check["ok"]:
            console.print(f"   [green]+[/green] {check['message']}")
        else:
            console.print(f"   [red]-[/red] {check['message']}")
            if check["fix_hint"]:
                console.print(f"       [dim]Fix: {check['fix_hint']}[/dim]")

    console.print("\n" + "=" * 40)
    if ok:
        console.print(
            "[bold green]+ All diagnostics passed! System is healthy.[/bold green]"
        )
    else:
        console.print(
            "[bold yellow]!  Some issues detected. See fix hints above.[/bold yellow]"
        )
    console.print("=" * 40 + "\n")
