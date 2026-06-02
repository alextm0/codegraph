"""Doctor command helper."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from codegraph.core.graph import get_database_manager
from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.logging import setup_logging

from codegraph.cli.commands._shared import console


def doctor_helper(config_path: Path | None = None) -> None:
    """Run health checks on config, Neo4j, GDS, and dependencies."""
    setup_logging(level=logging.WARNING)
    ok = True

    console.print("[bold cyan]Running CodeGraph Diagnostics...[/bold cyan]\n")

    # 0. Config file
    console.print("[bold]0. Checking Configuration...[/bold]")
    config_ok = False
    if config_path is None or not config_path.exists():
        console.print(
            f"   [red]-[/red] config.yaml not found at {config_path or 'unknown'}"
        )
        console.print(
            "       [dim]Fix: run [bold]codegraph init[/bold] to create it[/dim]"
        )
        ok = False
    else:
        raw = {}
        try:
            raw = load_raw_config(config_path)
            config_ok = True
            console.print(f"   [green]+[/green] Config found at {config_path}")
        except Exception as exc:
            console.print(f"   [red]-[/red] Could not read config: {exc}")
            ok = False

        if config_ok:
            proj_root = resolve_project_root(raw, config_path)
            if proj_root.exists():
                console.print(f"   [green]+[/green] Project root exists: {proj_root}")
            else:
                console.print(f"   [red]-[/red] Project root not found: {proj_root}")
                console.print(
                    "       [dim]Fix: update project_root in config.yaml[/dim]"
                )
                ok = False

            # Check password is available
            has_password = bool(
                os.getenv("NEO4J_PASSWORD") or raw.get("neo4j", {}).get("password")
            )
            if not has_password:
                console.print("   [red]-[/red] Neo4j password not set")
                console.print(
                    "       [dim]Fix: set NEO4J_PASSWORD in .env or run [bold]codegraph init[/bold][/dim]"
                )
                ok = False
            else:
                console.print("   [green]+[/green] Neo4j password available")

    db_manager = get_database_manager()
    connected = False

    # 1. Neo4j connectivity
    console.print("\n[bold]1. Checking Neo4j Connectivity...[/bold]")
    try:
        connected = db_manager.is_connected()
        if connected:
            uri = db_manager._config.uri if db_manager._config else "Neo4j"
            console.print(f"   [green]+[/green] Connected to {uri}")
        else:
            uri = (
                db_manager._config.uri
                if db_manager._config
                else "neo4j://localhost:7687"
            )
            console.print(f"   [red]-[/red] Cannot reach Neo4j at {uri}")
            console.print(
                "       [dim]Fix: start Neo4j (Neo4j Desktop → Start, or: neo4j start)[/dim]"
            )
            console.print("       [dim]Then verify at http://localhost:7474[/dim]")
            ok = False
    except Exception as exc:
        console.print(f"   [red]-[/red] Connection error: {exc}")
        console.print(
            "       [dim]Fix: check Neo4j is running and credentials are correct[/dim]"
        )
        ok = False

    # 2. GDS plugin
    console.print("\n[bold]2. Checking GDS Plugin...[/bold]")
    if connected:
        try:
            from codegraph.core.graph.ppr import create_gds_client

            gds = create_gds_client(db_manager.get_driver())
            version = gds.version()
            console.print(
                f"   [green]+[/green] GDS Plugin installed (version: {version})"
            )
        except Exception as exc:
            console.print(f"   [red]-[/red] GDS check failed: {exc}")
            console.print(
                "       [dim]Fix: install GDS in Neo4j Desktop → Plugins, or add to neo4j.conf[/dim]"
            )
            console.print(
                "       [dim]GDS is required for Personalized PageRank retrieval[/dim]"
            )
            ok = False
    else:
        console.print("   [yellow]![/yellow] SKIP (Neo4j not reachable)")

    # 3. Graph is indexed
    console.print("\n[bold]3. Checking Graph Index...[/bold]")
    if connected:
        try:
            from codegraph.core.graph.queries import count_nodes_by_label

            node_counts = count_nodes_by_label(db_manager.get_driver())
            total = sum(node_counts.values())
            if total > 0:
                console.print(f"   [green]+[/green] Graph has {total} nodes")
                if config_ok:
                    from codegraph.utils.graph_helpers import verify_graph_project_root

                    aligned, sample = verify_graph_project_root(
                        db_manager.get_driver(), proj_root
                    )
                    if aligned:
                        console.print(
                            f"   [green]+[/green] Indexed files resolve under project root"
                        )
                    else:
                        console.print(
                            "   [yellow]![/yellow] Graph may be out of sync with project_root"
                        )
                        console.print(f"       Sample missing file: {sample}")
                        console.print(
                            f"       Config project_root: {proj_root}"
                        )
                        console.print(
                            "       [dim]Fix: set project_root to the indexed repo, "
                            "then run [bold]codegraph rebuild[/bold][/dim]"
                        )
                        ok = False
            else:
                console.print("   [yellow]![/yellow] Graph is empty")
                console.print(
                    "       [dim]Fix: run [bold]codegraph rebuild[/bold] to index your project[/dim]"
                )
        except Exception as exc:
            console.print(f"   [yellow]![/yellow] Could not check graph: {exc}")
    else:
        console.print("   [yellow]![/yellow] SKIP (Neo4j not reachable)")

    # 4. tree-sitter installation
    console.print("\n[bold]4. Checking Tree-Sitter Installation...[/bold]")
    try:
        from tree_sitter import Language, Parser  # noqa: F401
        import tree_sitter_python  # noqa: F401

        console.print("   [green]+[/green] tree-sitter is installed")
        console.print("   [green]+[/green] python parser is available")
    except ImportError as e:
        console.print(f"   [red]-[/red] tree-sitter check failed: {e}")
        console.print(
            "       [dim]Fix: pip install tree-sitter tree-sitter-python[/dim]"
        )
        ok = False

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
