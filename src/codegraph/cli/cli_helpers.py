"""Helper functions for the CodeGraph CLI."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from neo4j import Driver
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box

from codegraph.utils.config import load_raw_config, resolve_project_root, parse_signal_weights
from codegraph.utils.logging import setup_logging
from codegraph.utils.ignore import load_ignore_patterns
from codegraph.core.graph import clear_database, build_graph, get_database_manager, load_full_config
from codegraph.core.graph.queries import (
    count_nodes_by_label, 
    count_edges_by_type, 
    get_most_connected_files,
    find_node_by_name,
    find_node_by_pattern,
    find_callers,
    find_callees,
    get_inheritance_chain,
    find_dead_code
)
from codegraph.core.parser import create_parser, parse_directory

logger = logging.getLogger(__name__)
console = Console()

def _initialize_db(config_path: Path):
    """Initialize the database manager with the given config."""
    db_manager = get_database_manager()
    db_manager.initialize(str(config_path))
    return db_manager

def visualize_helper(config_path: Path, port: int, no_browser: bool) -> None:
    """Start the FastAPI visualizer server and (optionally) open the browser."""
    setup_logging(level=logging.WARNING)

    raw_config = load_raw_config(config_path)
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

    fastapi_app = create_app(driver, raw_config)
    url = f"http://localhost:{port}"

    if not no_browser:
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    console.print(f"[green]CodeGraph Visualizer[/green] running at [bold cyan]{url}[/bold cyan]")
    console.print("Press [bold]Ctrl+C[/bold] to stop.\n")
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning")


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
                console.print("[bold red]ERROR:[/bold red] Cannot reach Neo4j. Is it running?")
                sys.exit(1)
        
        console.print("[green]✓[/green] Connected to Neo4j.")

        with console.status("[bold yellow]Clearing existing graph..."):
            deleted = clear_database(driver)
        console.print(f"[green]✓[/green] Cleared {deleted} nodes.")

        # Load ignore patterns
        ignore_file = project_root / ".cgignore"
        exclude = raw_config.get("parser", {}).get("exclude_patterns", [])
        exclude += raw_config.get("exclude_patterns", [])
        if ignore_file.exists():
            console.print(f"  Loading ignore patterns from [blue]{ignore_file.name}[/blue]")
            exclude.extend(load_ignore_patterns(ignore_file))

        console.print(f"Parsing: [bold cyan]{project_root}[/bold cyan]")
        parser = create_parser()
        
        all_entities = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            parse_task = progress.add_task("Parsing files...", total=None)
            
            def parse_progress(current: int, total: int, file_path: str) -> None:
                progress.update(parse_task, total=total, completed=current, description=f"Parsing {Path(file_path).name}")

            all_entities = parse_directory(
                str(project_root), parser, exclude_patterns=exclude,
                progress_callback=parse_progress,
            )
        console.print(f"[green]✓[/green] Parsed {len(all_entities)} files.")

        console.print("Building graph...")
        def graph_progress(stage: str, count: int) -> None:
            console.print(f"  {stage}: [bold]{count}[/bold]")

        create_colocation = raw_config.get("graph", {}).get("create_colocation_edges", False)
        counts = build_graph(
            driver, all_entities,
            progress_callback=graph_progress,
            create_colocation_edges=create_colocation,
        )

        total_nodes = sum(v for k, v in counts.items() if k in ("File", "Function", "Class", "Method"))
        total_edges = sum(v for k, v in counts.items() if k in ("CONTAINS", "CALLS", "IMPORTS", "INHERITS_FROM"))
        console.print(f"\n[bold green]Graph rebuild complete:[/bold green] {total_nodes} nodes, {total_edges} edges.")
    except Exception as e:
        console.print(f"[bold red]Error during rebuild:[/bold red] {e}")
        logger.exception("Rebuild failed")
        sys.exit(1)

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
                conn_table.add_row(str(row['entity_count']), row['file_path'])
            console.print(conn_table)
        console.print()
    except Exception as e:
        console.print(f"[bold red]Error fetching stats:[/bold red] {e}")

def doctor_helper() -> None:
    """Run health checks on Neo4j, GDS, and config."""
    setup_logging(level=logging.WARNING)
    ok = True

    db_manager = get_database_manager()
    
    console.print("[bold cyan]🏥 Running CodeGraph Diagnostics...[/bold cyan]\n")
    
    # 1. Neo4j connectivity
    console.print("[bold]1. Checking Neo4j Connectivity...[/bold]")
    try:
        connected = db_manager.is_connected()
        if connected:
            console.print(f"   [green]✓[/green] Connected to {db_manager._config.uri if db_manager._config else 'Neo4j'}")
        else:
            console.print(f"   [red]✗[/red] Cannot reach Neo4j at {db_manager._config.uri if db_manager._config else 'unknown'}")
            ok = False
    except Exception as exc:
        console.print(f"   [red]✗[/red] Connection error: {exc}")
        ok = False
        connected = False

    # 2. GDS plugin
    console.print("\n[bold]2. Checking GDS Plugin...[/bold]")
    if connected:
        try:
            from codegraph.core.graph.ppr import create_gds_client
            gds = create_gds_client(db_manager.get_driver())
            version = gds.version()
            console.print(f"   [green]✓[/green] GDS Plugin installed (version: {version})")
        except Exception as exc:
            console.print(f"   [red]✗[/red] GDS check failed: {exc}")
            console.print("       [dim]Note: GDS is required for Personalized PageRank (PPR) retrieval.[/dim]")
            ok = False
    else:
        console.print("   [yellow]⚠[/yellow] SKIP (Neo4j not reachable)")

    # 3. tree-sitter installation
    console.print("\n[bold]3. Checking Tree-Sitter Installation...[/bold]")
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_python
        console.print("   [green]✓[/green] tree-sitter is installed")
        console.print("   [green]✓[/green] python parser is available")
    except ImportError as e:
        console.print(f"   [red]✗[/red] tree-sitter check failed: {e}")
        ok = False

    console.print("\n" + "=" * 40)
    if ok:
        console.print("[bold green]✅ All diagnostics passed! System is healthy.[/bold green]")
    else:
        console.print("[bold yellow]⚠️  Some issues detected. Please review the output above.[/bold yellow]")
    console.print("=" * 40 + "\n")

def query_helper(
    config_path: Path,
    task: str,
    entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
) -> None:
    """Run the retrieval pipeline and print context to stdout."""
    setup_logging(level=logging.WARNING)

    raw_config = load_full_config(config_path)
    project_root_str = str(resolve_project_root(raw_config, config_path))

    from codegraph.core.graph.ppr import PPRConfig, create_gds_client
    from codegraph.core.retrieval.pipeline import run_retrieval_pipeline

    db_manager = get_database_manager()
    driver = db_manager.get_driver()
    try:
        if not db_manager.is_connected():
            console.print("[bold red]ERROR:[/bold red] Cannot reach Neo4j.")
            sys.exit(1)

        ppr_section = raw_config.get("ppr", {})
        mcp_section = raw_config.get("mcp", {})
        seed_section = raw_config.get("seed_selection", {})

        ppr_config = PPRConfig(
            damping_factor=ppr_section.get("damping_factor", 0.85),
            max_iterations=ppr_section.get("max_iterations", 20),
            tolerance=ppr_section.get("tolerance", 1e-7),
            top_k=top_k if top_k > 0 else ppr_section.get("top_k", 20),
        )
        effective_budget = token_budget if token_budget > 0 else mcp_section.get("default_token_budget", 6000)

        signal_weights = parse_signal_weights(seed_section)
        exclude_seed_paths = seed_section.get("exclude_seed_paths") or []

        gds = create_gds_client(driver)

        console.print(f"Running retrieval for: [bold cyan]{task!r}[/bold cyan]")
        if entities:
            console.print(f"  Seed entities: [yellow]{entities}[/yellow]")
        if current_file:
            console.print(f"  Current file:  [blue]{current_file}[/blue]")
        console.print()

        with console.status("[bold green]Executing retrieval pipeline..."):
            results = run_retrieval_pipeline(
                driver=driver,
                gds=gds,
                task_description=task,
                project_root=project_root_str,
                mentioned_entities=entities,
                current_file=current_file,
                ppr_config=ppr_config,
                signal_weights=signal_weights or None,
                token_budget=effective_budget,
                exclude_seed_paths=exclude_seed_paths or None,
            )

        if not results:
            console.print("[yellow]No results found. Is the graph built? Run: codegraph rebuild[/yellow]")
            return

        console.print(f"Found [bold]{len(results)}[/bold] context items:\n")
        for i, item in enumerate(results, start=1):
            console.print(f"[bold magenta]--- [{i}] {item.qualified_name} (score={item.relevance_score:.4f}, {item.token_count} tokens) ---[/bold magenta]")
            console.print(f"    File: [blue]{item.file_path}:{item.line_start}-{item.line_end}[/blue]")
            console.print()
            # Print first 20 lines of source
            lines = item.source_code.splitlines()
            preview = lines[:20]
            for line in preview:
                console.print(f"    {line}")
            if len(lines) > 20:
                console.print(f"    [dim]... ({len(lines) - 20} more lines)[/dim]")
            console.print()
    except Exception as e:
        console.print(f"[bold red]Error during query:[/bold red] {e}")
        logger.exception("Query failed")

def explain_helper(config_path: Path, task: str, top_k: int = 10) -> None:
    """Show seeds, PPR scores, and graph paths explaining why each file was returned."""
    setup_logging(level=logging.WARNING)

    raw_config = load_raw_config(config_path)
    seed_section = raw_config.get("seed_selection", {})
    signal_weights = parse_signal_weights(seed_section)
    exclude_seed_paths = seed_section.get("exclude_seed_paths") or []

    db_manager = _initialize_db(config_path)
    driver = db_manager.get_driver()

    from codegraph.core.retrieval.seed_selection import extract_seeds, prepare_bm25_index

    if not db_manager.is_connected():
        console.print("[bold red]ERROR:[/bold red] Cannot reach Neo4j.")
        return

    console.print(f'\nExplaining: [bold cyan]"{task}"[/bold cyan]\n')

    bm25_index, searchable_nodes = prepare_bm25_index(driver, exclude_paths=exclude_seed_paths or None)
    seeds = extract_seeds(
        driver,
        task_description=task,
        signal_weights=signal_weights,
        bm25_index=bm25_index,
        searchable_nodes=searchable_nodes,
        exclude_paths=exclude_seed_paths or None,
    )

    if not seeds.seeds:
        console.print("[yellow]No seeds found. Is the graph built? Run: codegraph rebuild[/yellow]")
        return

    seed_ids = list(seeds.seeds.keys())
    seed_names = _fetch_seed_names(driver, seed_ids)
    _print_seeds_table(seeds.seeds, seed_names)

    ppr_results = _run_ppr_for_explain(driver, seeds.seeds, raw_config)

    top_files = _deduplicate_to_top_files(ppr_results, top_k)
    _print_results_table(driver, seed_ids, top_files)


def _run_ppr_for_explain(
    driver: Driver,
    seed_weights: dict[int, float],
    raw_config: dict,
) -> list:
    """Build PPRConfig from raw_config, ensure graph is ready, and run PPR.

    Returns the raw list of PPRResult objects from run_ppr_from_node_ids.
    """
    from codegraph.core.graph.ppr import PPRConfig, create_gds_client, run_ppr_from_node_ids
    from codegraph.core.retrieval.pipeline import ensure_graph_ready

    ppr_section = raw_config.get("ppr", {})
    ppr_config = PPRConfig(
        damping_factor=ppr_section.get("damping_factor", 0.70),
        max_iterations=ppr_section.get("max_iterations", 20),
        tolerance=ppr_section.get("tolerance", 1e-7),
        top_k=ppr_section.get("top_k", 30),
    )
    gds = create_gds_client(driver)
    ensure_graph_ready(driver, gds)
    return run_ppr_from_node_ids(gds, driver, seed_weights, ppr_config)


def _fetch_seed_names(driver: Driver, seed_ids: list[int]) -> dict[int, str]:
    """Return {node_id: display_name} for a list of seed node IDs."""
    names: dict[int, str] = {}
    with driver.session() as session:
        result = session.run(
            "MATCH (n) WHERE id(n) IN $ids RETURN id(n) AS nid, "
            "coalesce(n.name, n.file_path, '') AS name",
            ids=seed_ids,
        )
        for r in result:
            names[r["nid"]] = r["name"] or ""
    return names


def _print_seeds_table(
    seed_weights: dict[int, float], seed_names: dict[int, str]
) -> None:
    """Print the seeds summary table to the console."""
    seeds_table = Table(title=f"Seeds ({len(seed_weights)} nodes)", box=box.SIMPLE_HEAVY)
    seeds_table.add_column("Seed node", style="cyan")
    seeds_table.add_column("Signal", style="magenta")
    seeds_table.add_column("Weight", justify="right", style="green")

    for nid, weight in sorted(seed_weights.items(), key=lambda x: -x[1]):
        name = seed_names.get(nid, str(nid))
        signal = "entity" if weight >= 0.3 else "bm25"
        seeds_table.add_row(name, signal, f"{weight:.3f}")
    console.print(seeds_table)


def _deduplicate_to_top_files(
    ppr_results: list, top_k: int
) -> list[tuple[str, float]]:
    """Deduplicate PPR results by file_path, keeping highest score per file.

    Returns list of (file_path, score) sorted descending, limited to top_k.
    """
    best: dict[str, float] = {}
    for r in ppr_results:
        fp = r.file_path
        if fp and (fp not in best or r.score > best[fp]):
            best[fp] = r.score
    return sorted(best.items(), key=lambda x: -x[1])[:top_k]


def _print_results_table(
    driver: Driver,
    seed_ids: list[int],
    top_files: list[tuple[str, float]],
) -> None:
    """Print the top results table with reasoning paths."""
    from codegraph.core.graph.queries import trace_path_to_seed

    results_table = Table(
        title="Top Results — Why did PPR return these?", box=box.SIMPLE_HEAVY
    )
    results_table.add_column("#", justify="right", style="bold")
    results_table.add_column("File", style="blue")
    results_table.add_column("Score", justify="right", style="green")
    results_table.add_column("Reasoning path from nearest seed", style="dim")

    for rank, (fp, score) in enumerate(top_files, start=1):
        path_str = trace_path_to_seed(driver, seed_ids, fp)
        results_table.add_row(str(rank), fp, f"{score:.5f}", path_str)

    console.print(results_table)
    console.print()


def find_name_helper(name: str):
    """Find nodes by name."""
    setup_logging(level=logging.WARNING)
    db_manager = get_database_manager()
    try:
        results = find_node_by_name(db_manager.get_driver(), name)
        if not results:
            console.print(f"[yellow]No nodes found with name '{name}'[/yellow]")
            return
        
        table = Table(title=f"Matches for '{name}'", box=box.ROUNDED)
        table.add_column("Qualified Name", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("File Path", style="blue")
        
        for res in results:
            table.add_row(res.qualified_name, res.label, res.file_path)
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error finding node:[/bold red] {e}")

def find_pattern_helper(pattern: str):
    """Find nodes by pattern."""
    setup_logging(level=logging.WARNING)
    db_manager = get_database_manager()
    try:
        results = find_node_by_pattern(db_manager.get_driver(), pattern)
        if not results:
            console.print(f"[yellow]No nodes found matching pattern '{pattern}'[/yellow]")
            return
        
        table = Table(title=f"Matches for pattern '{pattern}'", box=box.ROUNDED)
        table.add_column("Qualified Name", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("File Path", style="blue")
        
        for res in results:
            table.add_row(res.qualified_name, res.label, res.file_path)
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error finding node by pattern:[/bold red] {e}")

