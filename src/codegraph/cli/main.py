"""Main CLI implementation for CodeGraph."""

import os
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console

from codegraph.cli.cli_helpers import (
    rebuild_helper,
    stats_helper,
    doctor_helper,
    query_helper,
    find_name_helper,
    find_pattern_helper,
    _initialize_db
)

app = typer.Typer(
    name="codegraph",
    help="CodeGraph: A graph-based code context engine for AI-powered analysis.",
    add_completion=True,
)
console = Console()

# Global options
@app.callback()
def callback(
    config: str = typer.Option("config.yaml", help="Path to config.yaml")
):
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
def stats(ctx: typer.Context):
    """
    Show statistics about the current graph (nodes, edges, etc.).
    """
    config_path = get_config_path(ctx)
    _initialize_db(config_path)
    stats_helper()

@app.command()
def doctor(ctx: typer.Context):
    """
    Run diagnostics to check system health and configuration.
    """
    config_path = get_config_path(ctx)
    _initialize_db(config_path)
    doctor_helper()

@app.command()
def query(
    ctx: typer.Context,
    task: str = typer.Argument(..., help="Task description to retrieve context for"),
    entities: Optional[List[str]] = typer.Option(None, "--entity", "-e", help="Specific entity names to include as seeds"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Current file path (used as a low-weight seed hint)"),
    top_k: int = typer.Option(0, "--top-k", help="Max results (0 = use config default)"),
    budget: int = typer.Option(0, "--budget", help="Token budget (0 = use config default)"),
):
    """
    Run the retrieval pipeline to get context for a specific task.
    """
    config_path = get_config_path(ctx)
    _initialize_db(config_path)
    query_helper(config_path, task, entities, file, top_k, budget)

@app.command()
def serve(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(None, "--config", help="Config path passed to the MCP server")
):
    """
    Start the CodeGraph MCP server.
    """
    config_path = config or get_config_path(ctx)
    os.environ["CODEGRAPH_CONFIG"] = str(Path(config_path).resolve())
    from codegraph.mcp.server import main as serve_main
    serve_main()

# Find command group
find_app = typer.Typer(help="Search for entities in the code graph.")
app.add_typer(find_app, name="find")

@find_app.command("name")
def find_name(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Name of the entity to find")
):
    """Find an entity by its exact name."""
    config_path = get_config_path(ctx)
    _initialize_db(config_path)
    find_name_helper(name)

@find_app.command("pattern")
def find_pattern(
    ctx: typer.Context,
    pattern: str = typer.Argument(..., help="Pattern to search for (substring match)")
):
    """Find entities matching a substring pattern."""
    config_path = get_config_path(ctx)
    _initialize_db(config_path)
    find_pattern_helper(pattern)

# Analyze command group
analyze_app = typer.Typer(help="Analyze relationships and dependencies.")
app.add_typer(analyze_app, name="analyze")

@analyze_app.command("callers")
def analyze_callers(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Qualified name or name of the entity")
):
    """Find all entities that call the specified function/method."""
    config_path = get_config_path(ctx)
    _initialize_db(config_path)
    from codegraph.core.graph.queries import find_callers
    from rich.table import Table
    import rich.box as box
    
    db_manager = _initialize_db(config_path)
    results = find_callers(db_manager.get_driver(), name)
    if not results:
        console.print(f"[yellow]No callers found for '{name}'[/yellow]")
        return
    
    table = Table(title=f"Callers of '{name}'", box=box.ROUNDED)
    table.add_column("Qualified Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("File Path", style="blue")
    for res in results:
        table.add_row(res.qualified_name, res.label, res.file_path)
    console.print(table)

@analyze_app.command("callees")
def analyze_callees(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Qualified name or name of the entity")
):
    """Find all entities called by the specified function/method."""
    config_path = get_config_path(ctx)
    db_manager = _initialize_db(config_path)
    from codegraph.core.graph.queries import find_callees
    from rich.table import Table
    import rich.box as box
    
    results = find_callees(db_manager.get_driver(), name)
    if not results:
        console.print(f"[yellow]No callees found for '{name}'[/yellow]")
        return
    
    table = Table(title=f"Callees of '{name}'", box=box.ROUNDED)
    table.add_column("Qualified Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("File Path", style="blue")
    for res in results:
        table.add_row(res.qualified_name, res.label, res.file_path)
    console.print(table)

@analyze_app.command("deps")
def analyze_deps(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Entity name to find dependencies for"),
    direction: str = typer.Option("both", "--direction", "-d", help="upsteam, downstream, or both"),
    depth: int = typer.Option(1, "--depth", help="Search depth (1 or 2)")
):
    """Analyze dependencies and imports for an entity."""
    config_path = get_config_path(ctx)
    db_manager = _initialize_db(config_path)
    from codegraph.core.graph.queries import query_entity_dependencies
    from rich.table import Table
    import rich.box as box
    
    try:
        results = query_entity_dependencies(db_manager.get_driver(), name, direction, depth)
        if not results:
            console.print(f"[yellow]No dependencies found for '{name}'[/yellow]")
            return
        
        table = Table(title=f"Dependencies of '{name}' ({direction}, depth {depth})", box=box.ROUNDED)
        table.add_column("Qualified Name", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("File Path", style="blue")
        for res in results:
            table.add_row(res.qualified_name, res.label, res.file_path)
        console.print(table)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")

@analyze_app.command("dead-code")
def analyze_dead(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results")
):
    """Find functions and methods that are never called (potential dead code)."""
    config_path = get_config_path(ctx)
    db_manager = _initialize_db(config_path)
    from codegraph.core.graph.queries import find_dead_code
    from rich.table import Table
    import rich.box as box
    
    results = find_dead_code(db_manager.get_driver(), limit)
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
