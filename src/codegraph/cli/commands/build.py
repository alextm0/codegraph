"""Graph rebuild command helper."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from codegraph.core.graph import build_graph, clear_database
from codegraph.core.parser import create_parser, parse_directory
from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.ignore import load_ignore_patterns
from codegraph.utils.logging import setup_logging

from codegraph.cli.commands._shared import (
    _initialize_db,
    _write_build_timestamp,
    console,
    logger,
)


def rebuild_helper(config_path: Path) -> None:
    """Rebuild the graph with progress output."""
    setup_logging(level=logging.INFO)

    raw_config = load_raw_config(config_path)
    project_root = resolve_project_root(raw_config, config_path)

    db_manager = _initialize_db(config_path)
    driver = db_manager.get_driver()

    try:
        with console.status("[bold green]Connecting to Neo4j..."):
            if not db_manager.is_connected():
                console.print(
                    "[bold red]ERROR:[/bold red] Cannot reach Neo4j. Is it running?"
                )
                sys.exit(1)

        console.print("[green]+[/green] Connected to Neo4j.")

        with console.status("[bold yellow]Clearing existing graph..."):
            deleted = clear_database(driver)
        console.print(f"[green]+[/green] Cleared {deleted} nodes.")

        # Load ignore patterns
        ignore_file = project_root / ".cgignore"
        exclude = raw_config.get("parser", {}).get("exclude_patterns", [])
        exclude += raw_config.get("exclude_patterns", [])
        if ignore_file.exists():
            console.print(
                f"  Loading ignore patterns from [blue]{ignore_file.name}[/blue]"
            )
            exclude.extend(load_ignore_patterns(ignore_file))

        console.print(f"Parsing: [bold cyan]{project_root}[/bold cyan]")
        parser = create_parser()

        all_entities = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            parse_task = progress.add_task("Parsing files...", total=None)

            def parse_progress(current: int, total: int, file_path: str) -> None:
                progress.update(
                    parse_task,
                    total=total,
                    completed=current,
                    description=f"Parsing {Path(file_path).name}",
                )

            all_entities = parse_directory(
                str(project_root),
                parser,
                exclude_patterns=exclude,
                progress_callback=parse_progress,
            )
        console.print(f"[green]+[/green] Parsed {len(all_entities)} files.")

        console.print("Building graph...")

        def graph_progress(stage: str, count: int) -> None:
            console.print(f"  {stage}: [bold]{count}[/bold]")

        counts = build_graph(
            driver,
            all_entities,
            progress_callback=graph_progress,
        )

        total_nodes = sum(
            v for k, v in counts.items() if k in ("File", "Function", "Class", "Method")
        )
        total_edges = sum(
            v
            for k, v in counts.items()
            if k in ("CONTAINS", "CALLS", "IMPORTS", "INHERITS_FROM")
        )
        _write_build_timestamp(config_path)
        console.print(
            f"\n[bold green]Graph rebuild complete:[/bold green] {total_nodes} nodes, {total_edges} edges."
        )
    except Exception as e:
        console.print(f"[bold red]Error during rebuild:[/bold red] {e}")
        logger.exception("Rebuild failed")
        sys.exit(1)
