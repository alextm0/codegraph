"""Status and stats command helpers."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich import box
from rich.table import Table

from codegraph.core.graph import get_database_manager
from codegraph.core.graph.queries import (
    count_edges_by_type,
    count_nodes_by_label,
    get_most_connected_files,
)
from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.logging import setup_logging

from codegraph.cli.commands._shared import _read_build_timestamp, console
from codegraph.cli.commands.install import _find_mcp_registrations


def stats_helper() -> None:
    """Show node and edge counts."""
    setup_logging(level=logging.WARNING)

    db_manager = get_database_manager()
    driver = db_manager.get_driver()
    try:
        if not db_manager.is_connected():
            console.print("[bold red]ERROR:[/bold red] Cannot reach Neo4j.")
            sys.exit(1)

        node_counts = count_nodes_by_label(driver)
        edge_counts = count_edges_by_type(driver)
        most_connected = get_most_connected_files(driver, limit=5)

        console.print("\n[bold cyan]=== Graph Statistics ===[/bold cyan]\n")

        # Nodes Table
        node_table = Table(title="Nodes", box=box.ROUNDED)
        node_table.add_column("Label", style="magenta")
        node_table.add_column("Count", justify="right", style="green")

        total_nodes = 0
        for label, cnt in sorted(node_counts.items()):
            node_table.add_row(label, str(cnt))
            total_nodes += cnt
        node_table.add_section()
        node_table.add_row("TOTAL", str(total_nodes), style="bold")
        console.print(node_table)

        # Edges Table
        edge_table = Table(title="Edges", box=box.ROUNDED)
        edge_table.add_column("Type", style="magenta")
        edge_table.add_column("Count", justify="right", style="green")

        total_edges = 0
        for rel_type, cnt in sorted(edge_counts.items()):
            edge_table.add_row(rel_type, str(cnt))
            total_edges += cnt
        edge_table.add_section()
        edge_table.add_row("TOTAL", str(total_edges), style="bold")
        console.print(edge_table)

        if most_connected:
            conn_table = Table(title="Top files by entity count", box=box.ROUNDED)
            conn_table.add_column("Count", justify="right", style="green")
            conn_table.add_column("File Path", style="blue")
            for row in most_connected:
                conn_table.add_row(str(row["entity_count"]), row["file_path"])
            console.print(conn_table)
        console.print()
    except Exception as e:
        console.print(f"[bold red]Error fetching stats:[/bold red] {e}")
        sys.exit(1)


def status_helper(config_path: Path) -> None:
    """Show current CodeGraph state: project root, graph counts, last build, MCP registration."""
    setup_logging(level=logging.WARNING)

    console.print("\n[bold cyan]=== CodeGraph Status ===[/bold cyan]\n")

    # Config
    if not config_path.exists():
        console.print(f"[red]-[/red] No config found at {config_path}")
        console.print("  Run [bold]codegraph init[/bold] to set up.\n")
        return

    raw = load_raw_config(config_path)
    project_root = resolve_project_root(raw, config_path)
    console.print(f"[bold]Config:[/bold]    {config_path}")
    console.print(f"[bold]Project:[/bold]   {project_root}")

    # Last build timestamp
    ts = _read_build_timestamp(config_path)
    if ts:
        console.print(f"[bold]Last build:[/bold] {ts} UTC")
    else:
        console.print(
            "[bold]Last build:[/bold] [yellow]unknown (run codegraph rebuild)[/yellow]"
        )

    # Neo4j graph stats
    console.print()
    db_manager = get_database_manager()
    try:
        connected = db_manager.is_connected()
    except Exception:
        connected = False

    if connected:
        try:
            driver = db_manager.get_driver()
            node_counts = count_nodes_by_label(driver)
            edge_counts = count_edges_by_type(driver)
            total_nodes = sum(node_counts.values())
            total_edges = sum(edge_counts.values())
            console.print(
                f"[bold]Graph:[/bold]     {total_nodes} nodes, {total_edges} edges"
            )
            if total_nodes == 0:
                console.print(
                    "             [yellow]Graph is empty — run codegraph rebuild[/yellow]"
                )
        except Exception as e:
            console.print(
                f"[bold]Graph:[/bold]     [yellow]could not fetch counts: {e}[/yellow]"
            )
    else:
        console.print(
            "[bold]Graph:[/bold]     [yellow]Neo4j not reachable — run codegraph doctor[/yellow]"
        )

    # MCP registration
    console.print()
    mcp_locations = _find_mcp_registrations(config_path)
    if mcp_locations:
        for loc in mcp_locations:
            console.print(f"[bold]MCP:[/bold]       [green]registered[/green] in {loc}")
    else:
        console.print(
            "[bold]MCP:[/bold]       [yellow]not registered — run codegraph install[/yellow]"
        )

    console.print()
