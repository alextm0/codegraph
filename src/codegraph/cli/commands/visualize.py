"""Visualize command helper."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.logging import setup_logging

from codegraph.cli.commands._shared import _initialize_db, console


def visualize_helper(
    config_path: Path,
    port: int,
    no_browser: bool,
    dev: bool = False,
    watch: bool = False,
    initial_task: str | None = None,
) -> None:
    """Start the FastAPI visualizer server and (optionally) open the browser."""
    setup_logging(level=logging.WARNING)

    raw_config = load_raw_config(config_path)
    project_root = resolve_project_root(raw_config, config_path)
    db_manager = _initialize_db(config_path)
    driver = db_manager.get_driver()

    if not db_manager.is_connected():
        console.print("[bold red]ERROR:[/bold red] Cannot reach Neo4j. Is it running?")
        sys.exit(1)

    try:
        import uvicorn
    except ImportError:
        console.print(
            "[bold red]ERROR:[/bold red] uvicorn is required for the visualizer.\n"
            "Install it with: [bold]pip install -e '.[visualizer]'[/bold]"
        )
        sys.exit(1)

    from codegraph.visualizer.server import create_app

    dist_index = (
        Path(__file__).resolve().parents[2]
        / "visualizer"
        / "static"
        / "dist"
        / "index.html"
    )
    if not dev and not dist_index.exists():
        console.print(
            "[yellow]WARNING:[/yellow] Frontend not built — UI will not load."
        )
        console.print(
            "  [dim]Run: [bold]cd frontend && npm run build[/bold][/dim]"
        )
        console.print(
            "  [dim]Or use [bold]codegraph visualize --dev[/bold] with "
            "[bold]cd frontend && npm run dev[/bold][/dim]\n"
        )

    fastapi_app = create_app(
        driver,
        raw_config,
        project_root=str(project_root),
        config_path=config_path,
        dev_mode=dev,
        watch_mode=watch,
    )
    url = f"http://localhost:{port}"

    if dev:
        console.print(
            f"[yellow]Dev mode:[/yellow] API only on port {port}. "
            "Run [bold]cd frontend && npm run dev[/bold] for the frontend."
        )
    else:
        if not no_browser:
            import threading
            import webbrowser
            from urllib.parse import urlencode

            browser_url = (
                f"{url}/?{urlencode({'task': initial_task})}" if initial_task else url
            )
            threading.Timer(1.0, lambda: webbrowser.open(browser_url)).start()

    console.print(
        f"[green]CodeGraph Visualizer[/green] running at [bold cyan]{url}[/bold cyan]"
    )
    console.print("Press [bold]Ctrl+C[/bold] to stop.\n")
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
