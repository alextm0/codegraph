"""Main CLI implementation for CodeGraph."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from codegraph.cli.cli_helpers import (
    rebuild_helper,
    stats_helper,
    doctor_helper,
    query_helper,
    explain_helper,
    visualize_helper,
    init_helper,
    install_helper,
    status_helper,
    watch_helper,
    _initialize_db,
)

app = typer.Typer(
    name="codegraph",
    help="CodeGraph: A graph-based code context engine for AI-powered analysis.",
    add_completion=True,
)
console = Console()


# Global options
@app.callback()
def callback(config: str = typer.Option("config.yaml", help="Path to config.yaml")):
    """
    CodeGraph CLI.
    """
    config_path = Path(config).resolve()
    if not config_path.exists():
        # Try local project config if not absolute
        config_path = Path.cwd() / "config.yaml"

    # Store config_path in context for subcommands
    # But for simplicity, we'll just initialize DB here if it's a command that needs it
    pass


def get_config_path(ctx: typer.Context) -> Path:
    config = ctx.parent.params.get("config", "config.yaml")
    config_path = Path(config).resolve()
    if not config_path.exists():
        config_path = Path.cwd() / "config.yaml"
    return config_path


@app.command()
def rebuild(ctx: typer.Context):
    """
    Clear and rebuild the code graph from the current project.
    """
    config_path = get_config_path(ctx)
    rebuild_helper(config_path)


@app.command()
def init(
    ctx: typer.Context,
    target: str = typer.Argument(None, help="Local path or GitHub URL to index"),
):
    """
    Initialize a new CodeGraph project with an interactive wizard.
    """
    config_path = get_config_path(ctx)
    init_helper(config_path, target)


@app.command()
def install(ctx: typer.Context):
    """
    Register CodeGraph MCP server with Claude Code or Claude Desktop.

    Writes .mcp.json (Claude Code) or updates the global claude.json (Claude Desktop).
    Run this once after codegraph init to make the server visible to your AI assistant.
    """
    config_path = get_config_path(ctx)
    install_helper(config_path)


@app.command()
def status(ctx: typer.Context):
    """
    Show current CodeGraph state: project, graph counts, last build, MCP registration.
    """
    config_path = get_config_path(ctx)
    try:
        _initialize_db(config_path)
    except ValueError:
        pass  # status_helper will show what's missing
    status_helper(config_path)


@app.command()
def watch(ctx: typer.Context):
    """
    Watch for file changes and update the graph incrementally.
    """
    config_path = get_config_path(ctx)
    watch_helper(config_path)


@app.command()
def stats(ctx: typer.Context):
    """
    Show statistics about the current graph (nodes, edges, etc.).
    """
    config_path = get_config_path(ctx)
    try:
        _initialize_db(config_path)
    except ValueError as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        console.print(
            "[dim]Fix: run [bold]codegraph init[/bold] or set NEO4J_PASSWORD in .env[/dim]"
        )
        raise typer.Exit(1)
    stats_helper()


@app.command()
def doctor(ctx: typer.Context):
    """
    Run diagnostics to check system health and configuration.
    """
    config_path = get_config_path(ctx)
    try:
        _initialize_db(config_path)
    except ValueError:
        pass  # doctor_helper will report the missing credentials itself
    doctor_helper(config_path)


@app.command()
def query(
    ctx: typer.Context,
    task: str = typer.Argument(..., help="Task description to retrieve context for"),
    entities: list[str] | None = typer.Option(
        None, "--entity", "-e", help="Specific entity names to include as seeds"
    ),
    top_k: int = typer.Option(
        0, "--top-k", help="Max results (0 = use config default)"
    ),
    budget: int = typer.Option(
        0, "--budget", help="Token budget (0 = use config default)"
    ),
    viz: bool = typer.Option(
        False, "--viz", help="Open visualizer after running query"
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Output results as machine-readable JSON"
    ),
    compact: bool = typer.Option(
        False, "--compact", help="Compact output: file paths and scores only"
    ),
    trace: bool = typer.Option(
        False, "--trace", help="Emit structured retrieval trace as JSON"
    ),
):
    """
    Run the retrieval pipeline to get context for a specific task.
    """
    config_path = get_config_path(ctx)
    try:
        _initialize_db(config_path)
    except ValueError as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        console.print(
            "[dim]Fix: run [bold]codegraph init[/bold] or set NEO4J_PASSWORD in .env[/dim]"
        )
        raise typer.Exit(1)
    query_helper(
        config_path,
        task,
        entities,
        top_k,
        budget,
        json_out=json_out,
        compact=compact,
        trace=trace,
    )

    if viz:
        visualize_helper(config_path, port=8474, no_browser=False, initial_task=task)


@app.command()
def explain(
    ctx: typer.Context,
    task: str = typer.Argument(..., help="Task description to explain retrieval for"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of files to explain"),
    trace: bool = typer.Option(
        False, "--trace", help="Emit structured retrieval trace as JSON"
    ),
) -> None:
    """
    Explain why PPR returned specific files for a task — shows seeds and reasoning paths.
    """
    config_path = get_config_path(ctx)
    try:
        _initialize_db(config_path)
    except ValueError as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        console.print(
            "[dim]Fix: run [bold]codegraph init[/bold] or set NEO4J_PASSWORD in .env[/dim]"
        )
        raise typer.Exit(1)
    explain_helper(config_path, task, top_k, trace=trace)


@app.command()
def visualize(
    ctx: typer.Context,
    port: int = typer.Option(8474, "--port", "-p", help="Port to listen on"),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't open browser automatically"
    ),
    dev: bool = typer.Option(
        False,
        "--dev",
        help="API-only mode for Vite dev server (run 'cd frontend && npm run dev' separately)",
    ),
    watch: bool = typer.Option(
        False, "--watch", help="Enable file watching and live updates"
    ),
) -> None:
    """
    Start the interactive CodeGraph visualizer in your browser.

    Shows a D3 force graph with PPR heat scores, seed nodes, and reasoning paths.
    """
    config_path = get_config_path(ctx)
    _initialize_db(config_path)
    visualize_helper(config_path, port, no_browser, dev=dev, watch=watch)


@app.command()
def serve(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None, "--config", help="Config path passed to the MCP server"
    ),
):
    """
    Start the CodeGraph MCP server.
    """
    config_path = config or get_config_path(ctx)
    os.environ["CODEGRAPH_CONFIG"] = str(Path(config_path).resolve())
    from codegraph.mcp.server import main as serve_main

    serve_main()


@app.command("find")
def find_symbol(
    ctx: typer.Context,
    pattern: str = typer.Argument(..., help="Symbol or path substring to search"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum results"),
    label: str | None = typer.Option(
        None, "--type", "-t", help="Filter by node label (Function, Class, Method, File)"
    ),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search indexed symbols and files by name or path (fast graph lookup)."""
    config_path = get_config_path(ctx)
    try:
        db_manager = _initialize_db(config_path)
    except ValueError as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        console.print(
            "[dim]Fix: run [bold]codegraph init[/bold] or set NEO4J_PASSWORD in .env[/dim]"
        )
        raise typer.Exit(1)

    from codegraph.core.graph.queries import search_symbols
    from codegraph.utils.config import load_raw_config, resolve_project_root
    from codegraph.utils.paths import graph_file_path_scope, make_relative_path
    import json as json_mod
    import rich.box as box
    from rich.table import Table

    raw = load_raw_config(config_path)
    project_root = str(resolve_project_root(raw, config_path))
    scope = graph_file_path_scope(project_root)

    try:
        results = search_symbols(
            db_manager.get_driver(),
            pattern=pattern,
            limit=limit,
            label=label,
            project_scope=scope,
        )
    except Exception as e:
        console.print(f"[bold red]Search failed:[/bold red] {e}")
        raise typer.Exit(1)

    if json_out:
        payload = [
            {
                "qualified_name": r.qualified_name,
                "name": r.name,
                "label": r.label,
                "file_path": make_relative_path(r.file_path, project_root),
            }
            for r in results
        ]
        console.print(json_mod.dumps({"result_count": len(payload), "results": payload}, indent=2))
        return

    if not results:
        console.print(f"[yellow]No symbols matching '{pattern}'[/yellow]")
        return

    table = Table(title=f"Symbols matching '{pattern}'", box=box.ROUNDED)
    table.add_column("Qualified Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("File Path", style="blue")
    for res in results:
        table.add_row(
            res.qualified_name,
            res.label,
            make_relative_path(res.file_path, project_root),
        )
    console.print(table)


# Analyze command group
analyze_app = typer.Typer(help="Analyze relationships and dependencies.")
app.add_typer(analyze_app, name="analyze")


@analyze_app.command("deps")
def analyze_deps(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Entity name to find dependencies for"),
    direction: str = typer.Option(
        "both", "--direction", "-d", help="upstream, downstream, or both"
    ),
    depth: int = typer.Option(1, "--depth", help="Search depth (1 or 2)"),
    viz: bool = typer.Option(False, "--viz", help="Open visualizer for results"),
):
    """Analyze callers, callees, and imports for an entity.

    Use --direction upstream to find callers, downstream for callees, both for all.
    """
    config_path = get_config_path(ctx)
    try:
        db_manager = _initialize_db(config_path)
    except ValueError as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        console.print(
            "[dim]Fix: run [bold]codegraph init[/bold] or set NEO4J_PASSWORD in .env[/dim]"
        )
        raise typer.Exit(1)
    from codegraph.core.graph.queries import query_entity_dependencies
    from rich.table import Table
    import rich.box as box

    try:
        results = query_entity_dependencies(
            db_manager.get_driver(), name, direction, depth
        )
        if not results:
            console.print(f"[yellow]No dependencies found for '{name}'[/yellow]")
            return

        table = Table(
            title=f"Dependencies of '{name}' ({direction}, depth {depth})",
            box=box.ROUNDED,
        )
        table.add_column("Qualified Name", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Relationship", style="yellow")
        table.add_column("File Path", style="blue")
        for res in results:
            table.add_row(
                res.qualified_name,
                res.label,
                res.relationship_type or "",
                res.file_path,
            )
        console.print(table)

        if viz:
            visualize_helper(config_path, port=8474, no_browser=False)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print(
            "[dim]Use [bold]codegraph query[/bold] to confirm the entity name exists[/dim]"
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@analyze_app.command("dead-code")
def analyze_dead(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results"),
):
    """Find functions and methods that are never called (potential dead code)."""
    config_path = get_config_path(ctx)
    try:
        db_manager = _initialize_db(config_path)
    except ValueError as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        console.print(
            "[dim]Fix: run [bold]codegraph init[/bold] or set NEO4J_PASSWORD in .env[/dim]"
        )
        raise typer.Exit(1)
    from codegraph.core.graph.queries import find_dead_code
    from rich.table import Table
    import rich.box as box

    try:
        results = find_dead_code(db_manager.get_driver(), limit)
    except Exception as e:
        console.print(f"[bold red]Error running dead code analysis:[/bold red] {e}")
        raise typer.Exit(1)

    if not results:
        console.print("[green]No potential dead code found![/green]")
        return

    table = Table(title="Potential Dead Code", box=box.ROUNDED)
    table.add_column("Qualified Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("File Path", style="blue")
    for res in results:
        table.add_row(res.qualified_name, res.label, res.file_path)
    console.print(table)


def cli():
    app()


if __name__ == "__main__":
    cli()
