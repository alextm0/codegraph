"""Watch command helper."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.logging import setup_logging

from codegraph.cli.commands._shared import _initialize_db, console


def watch_helper(config_path: Path) -> None:
    """Watch for file changes and update the graph incrementally."""
    from codegraph.watcher.file_watcher import CodeGraphWatcher
    from codegraph.watcher.incremental import update_file_in_graph

    setup_logging(level=logging.INFO)
    raw_config = load_raw_config(config_path)
    project_root = resolve_project_root(raw_config, config_path)
    db_manager = _initialize_db(config_path)
    driver = db_manager.get_driver()

    if not db_manager.is_connected():
        console.print("[bold red]ERROR:[/bold red] Cannot reach Neo4j.")
        return

    exclude = raw_config.get("parser", {}).get("exclude_patterns", [])

    def on_changes(paths: set[str]):
        for p in paths:
            try:
                update_file_in_graph(driver, str(project_root), p)
                console.print(
                    f"[dim]{time.strftime('%H:%M:%S')}[/dim] [green]Updated:[/green] {Path(p).name}"
                )
            except Exception as e:
                console.print(f"[red]Error updating {p}:[/red] {e}")

    watcher = CodeGraphWatcher(str(project_root), on_changes, exclude_patterns=exclude)
    watcher.start()

    console.print(f"[bold green]Watching for changes in {project_root}...[/bold green]")
    console.print("Press [bold]Ctrl+C[/bold] to stop.")

    try:
        while True:
            watcher.check_for_changes()
            time.sleep(0.5)
    except KeyboardInterrupt:
        watcher.stop()
        console.print("\n[yellow]Stopped watching.[/yellow]")
