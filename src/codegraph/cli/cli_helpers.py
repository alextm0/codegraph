"""Helper functions for the CodeGraph CLI."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from neo4j import Driver
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.prompt import Prompt, Confirm
from rich import box

from codegraph.utils.config import (
    load_raw_config,
    save_raw_config,
    resolve_project_root,
    parse_signal_weights,
)
from codegraph.utils.logging import setup_logging
from codegraph.utils.ignore import load_ignore_patterns
from codegraph.core.graph import (
    clear_database,
    build_graph,
    get_database_manager,
    load_full_config,
)
from codegraph.core.graph.queries import (
    count_nodes_by_label,
    count_edges_by_type,
    get_most_connected_files,
)
from codegraph.core.parser import create_parser, parse_directory

logger = logging.getLogger(__name__)
console = Console()


def _initialize_db(config_path: Path):
    """Initialize the database manager with the given config."""
    db_manager = get_database_manager()
    db_manager.initialize(str(config_path))
    return db_manager


def init_helper(config_path: Path, target: str | None = None) -> None:
    """Run an interactive setup wizard to create/update config.yaml and clone/index."""
    import subprocess
    
    console.print("\n[bold cyan]CodeGraph Setup Wizard[/bold cyan]\n")

    if not target:
        target = Prompt.ask("[bold blue]Enter a local folder path or GitHub URL to index[/bold blue]", default=".")
        
    project_root = "."
    if target.startswith("http://") or target.startswith("https://"):
        repo_name = target.rstrip("/").split("/")[-1].replace(".git", "")
        clone_path = Path.cwd() / repo_name
        console.print(f"\n[bold yellow]Cloning {target} into {clone_path}...[/bold yellow]")
        try:
            subprocess.run(["git", "clone", target, str(clone_path)], check=True)
            project_root = str(clone_path)
            console.print("   [green]+[/green] Cloned successfully!")
        except subprocess.CalledProcessError as e:
            console.print(f"   [red]-[/red] Clone failed: {e}")
            return
    else:
        project_root = str(Path(target).resolve())

    if config_path.exists():
        if not Confirm.ask(
            f"\nConfig file [blue]{config_path.name}[/blue] already exists. Overwrite?"
        ):
            return

    # 1. Neo4j Settings
    console.print("\n[bold]1. Database Connection[/bold]")
    console.print("   [dim]CodeGraph requires Neo4j 5.x with the GDS plugin.[/dim]")
    console.print(
        "   [dim]Download: https://neo4j.com/deployment-center/ (Community Edition is free)[/dim]\n"
    )
    uri = Prompt.ask("Neo4j URI", default="neo4j://localhost:7687")
    user = Prompt.ask("Neo4j Username", default="neo4j")
    password = Prompt.ask("Neo4j Password", password=True)

    # Test connectivity
    connected = False
    with console.status("[yellow]Testing connectivity..."):
        try:
            from codegraph.core.graph.connection import Neo4jConfig
            from codegraph.core.graph.database import DatabaseManager

            test_config = Neo4jConfig(
                uri=uri, username=user, password=password, database="neo4j"
            )
            test_mgr = DatabaseManager()
            test_mgr._config = test_config
            connected = test_mgr.is_connected()
        except Exception:
            connected = False

    if connected:
        console.print("   [green]+[/green] Connected successfully!")
    else:
        console.print("   [red]-[/red] Connection failed.")
        console.print(
            "   [dim]Make sure Neo4j is running: check Neo4j Desktop or run 'neo4j start'[/dim]"
        )
        console.print("   [dim]Then verify credentials at http://localhost:7474[/dim]")
        if not Confirm.ask("Continue and save config anyway?"):
            return

    # 2. Project Settings
    console.print("\n[bold]2. Project Settings[/bold]")
    
    # We already have project_root from the target, but let user confirm
    project_root = Prompt.ask(
        "Project root directory (absolute or relative to config)", default=project_root
    )
    resolved = (
        (config_path.parent / project_root).resolve()
        if not Path(project_root).is_absolute()
        else Path(project_root)
    )
    if not resolved.exists():
        console.print(f"   [red]-[/red] Directory not found: {resolved}")
        if not Confirm.ask("Use it anyway?"):
            return

    # 3. Exclude Patterns
    exclude = [".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"]
    console.print(
        f"\n[bold]3. Default exclusions:[/bold] [dim]{', '.join(exclude)}[/dim]"
    )

    # Write password to .env, not config.yaml
    env_file = config_path.parent / ".env"
    _write_env_password(env_file, password)
    console.print(
        f"   [green]+[/green] Password written to [blue]{env_file.name}[/blue] (not stored in config.yaml)"
    )

    config_data = {
        "neo4j": {
            "uri": uri,
            "username": user,
        },
        "project_root": project_root,
        "exclude_patterns": exclude,
        "ppr": {
            "damping_factor": 0.70,
            "max_iterations": 20,
            "tolerance": 1.0e-7,
            "top_k": 30,
            "retrieval_mode": "uniform",
        },
        "seed_selection": {
            "entity_match_weight": 0.6,
            "bm25_weight": 0.3,
            "current_file_weight": 0.1,
            "bm25_top_n": 10,
            "exclude_seed_paths": ["tests/", "test_"],
        },
        "mcp": {
            "server_name": "codegraph",
            "default_token_budget": 6000,
            "default_top_k": 15,
        },
    }

    save_raw_config(config_path, config_data)
    console.print(f"\n[bold green]+ Configuration saved to {config_path}[/bold green]")

    # Create .cgignore if it doesn't exist
    resolved_root = resolve_project_root(config_data, config_path)
    ignore_file = resolved_root / ".cgignore"
    if not ignore_file.exists():
        if Confirm.ask("Create [blue].cgignore[/blue] with default patterns?"):
            with open(ignore_file, "w", encoding="utf-8") as f:
                f.write("# CodeGraph ignore patterns\n")
                for p in exclude:
                    f.write(f"{p}\n")
            console.print(f"   [green]+[/green] Created {ignore_file}")

    if target and (target.startswith("http://") or target.startswith("https://")):
        console.print(f"\n[bold green]Auto-indexing {project_root}...[/bold green]")
        rebuild_helper(config_path)
    else:
        if Confirm.ask("\nRun [bold]codegraph rebuild[/bold] now?", default=True):
            rebuild_helper(config_path)


def _write_env_password(env_file: Path, password: str) -> None:
    """Write NEO4J_PASSWORD to .env, preserving other existing entries."""
    lines: list[str] = []
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    new_lines = [line for line in lines if not line.startswith("NEO4J_PASSWORD=")]
    new_lines.append(f"NEO4J_PASSWORD={password}\n")
    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


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
            import os

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


def query_helper(
    config_path: Path,
    task: str,
    entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
    json_out: bool = False,
    compact: bool = False,
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
            damping_factor=ppr_section.get("damping_factor", 0.70),
            max_iterations=ppr_section.get("max_iterations", 20),
            tolerance=ppr_section.get("tolerance", 1e-7),
            top_k=top_k if top_k > 0 else ppr_section.get("top_k", 30),
        )
        effective_budget = (
            token_budget
            if token_budget > 0
            else mcp_section.get("default_token_budget", 6000)
        )

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
            if json_out:
                import json

                console.print(json.dumps({"results": [], "total": 0}))
            else:
                console.print(
                    "[yellow]No results found. Is the graph built? Run: codegraph rebuild[/yellow]"
                )
            return

        if json_out:
            import json

            output = {
                "total": len(results),
                "results": [
                    {
                        "rank": i,
                        "qualified_name": item.qualified_name,
                        "entity_type": item.entity_type,
                        "file_path": item.file_path,
                        "lines": [item.line_start, item.line_end],
                        "relevance_score": round(item.relevance_score, 4),
                        "token_count": item.token_count,
                    }
                    for i, item in enumerate(results, start=1)
                ],
            }
            console.print(json.dumps(output, indent=2))
            return

        if compact:
            for i, item in enumerate(results, start=1):
                console.print(
                    f"[bold]{i:>2}.[/bold] [blue]{item.file_path}[/blue]  [dim]score={item.relevance_score:.4f}[/dim]"
                )
            return

        console.print(f"Found [bold]{len(results)}[/bold] context items:\n")
        for i, item in enumerate(results, start=1):
            console.print(
                f"[bold magenta]--- [{i}] {item.qualified_name} (score={item.relevance_score:.4f}, {item.token_count} tokens) ---[/bold magenta]"
            )
            console.print(
                f"    File: [blue]{item.file_path}:{item.line_start}-{item.line_end}[/blue]"
            )
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

    from codegraph.core.retrieval.seed_selection import (
        extract_seeds,
        prepare_bm25_index,
    )

    if not db_manager.is_connected():
        console.print("[bold red]ERROR:[/bold red] Cannot reach Neo4j.")
        return

    console.print(f'\nExplaining: [bold cyan]"{task}"[/bold cyan]\n')

    bm25_index, searchable_nodes = prepare_bm25_index(
        driver, exclude_paths=exclude_seed_paths or None
    )
    seeds = extract_seeds(
        driver,
        task_description=task,
        signal_weights=signal_weights,
        bm25_index=bm25_index,
        searchable_nodes=searchable_nodes,
        exclude_paths=exclude_seed_paths or None,
    )

    if not seeds.seeds:
        console.print(
            "[yellow]No seeds found. Is the graph built? Run: codegraph rebuild[/yellow]"
        )
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
    from codegraph.core.graph.ppr import (
        PPRConfig,
        create_gds_client,
        run_ppr_from_node_ids,
    )
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
    seeds_table = Table(
        title=f"Seeds ({len(seed_weights)} nodes)", box=box.SIMPLE_HEAVY
    )
    seeds_table.add_column("Seed node", style="cyan")
    seeds_table.add_column("Signal", style="magenta")
    seeds_table.add_column("Weight", justify="right", style="green")

    for nid, weight in sorted(seed_weights.items(), key=lambda x: -x[1]):
        name = seed_names.get(nid, str(nid))
        signal = "entity" if weight >= 0.3 else "bm25"
        seeds_table.add_row(name, signal, f"{weight:.3f}")
    console.print(seeds_table)


def _deduplicate_to_top_files(ppr_results: list, top_k: int) -> list[tuple[str, float]]:
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


def watch_helper(config_path: Path) -> None:
    """Watch for file changes and update the graph incrementally."""
    from codegraph.watcher.file_watcher import CodeGraphWatcher
    from codegraph.watcher.incremental import update_file_in_graph
    import time

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


# ---------------------------------------------------------------------------
# Timestamp helpers (used by rebuild and status)
# ---------------------------------------------------------------------------

_TIMESTAMP_FILE_NAME = ".codegraph_last_built"


def _write_build_timestamp(config_path: Path) -> None:
    """Write current UTC timestamp next to config.yaml after a successful rebuild."""
    import datetime

    ts_file = config_path.parent / _TIMESTAMP_FILE_NAME
    ts_file.write_text(
        datetime.datetime.now(datetime.UTC).isoformat(), encoding="utf-8"
    )


def _read_build_timestamp(config_path: Path) -> str | None:
    """Return ISO timestamp string of last rebuild, or None if not found."""
    ts_file = config_path.parent / _TIMESTAMP_FILE_NAME
    if ts_file.exists():
        return ts_file.read_text(encoding="utf-8").strip()
    return None


def _gemini_settings_paths() -> list[Path]:
    """Return candidate paths for Gemini CLI settings.json."""
    return [Path.home() / ".gemini" / "settings.json"]


def _gemini_settings_has_codegraph(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return "codegraph" in data.get("mcpServers", {})
    except Exception:
        return False


# ---------------------------------------------------------------------------
# codegraph status
# ---------------------------------------------------------------------------


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


def _find_mcp_registrations(config_path: Path) -> list[str]:
    """Return list of config file paths where codegraph MCP server is registered."""
    found: list[str] = []

    # Project-level .mcp.json (Claude Code)
    project_mcp = config_path.parent / ".mcp.json"
    if _mcp_json_has_codegraph(project_mcp):
        found.append(str(project_mcp))

    # Project-level .gemini/settings.json (Gemini CLI)
    project_gemini = config_path.parent / ".gemini" / "settings.json"
    if _gemini_settings_has_codegraph(project_gemini):
        found.append(str(project_gemini))

    # Claude Desktop global config
    for candidate in _claude_desktop_config_paths():
        if _claude_json_has_codegraph(candidate):
            found.append(str(candidate))

    # Gemini CLI global config
    for candidate in _gemini_settings_paths():
        if _gemini_settings_has_codegraph(candidate):
            found.append(str(candidate))

    return found


def _mcp_json_has_codegraph(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return "codegraph" in data.get("mcpServers", {})
    except Exception:
        return False


def _claude_json_has_codegraph(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return "codegraph" in data.get("mcpServers", {})
    except Exception:
        return False


def _claude_desktop_config_paths() -> list[Path]:
    """Return candidate paths for Claude Desktop's claude.json on all platforms."""
    import platform

    system = platform.system()
    if system == "Darwin":
        return [
            Path.home() / "Library" / "Application Support" / "Claude" / "claude.json"
        ]
    if system == "Windows":
        appdata = Path(
            os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        )
        return [appdata / "Claude" / "claude.json"]
    # Linux
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return [xdg / "Claude" / "claude.json"]


# ---------------------------------------------------------------------------
# codegraph install
# ---------------------------------------------------------------------------


def install_helper(config_path: Path) -> None:
    """Write MCP server registration for Claude Code, Claude Desktop, or Gemini CLI."""
    import shutil

    console.print("\n[bold cyan]CodeGraph MCP Install Wizard[/bold cyan]\n")

    if not config_path.exists():
        console.print(
            "[red]-[/red] config.yaml not found. Run [bold]codegraph init[/bold] first."
        )
        return

    # Resolve codegraph executable path
    codegraph_exe = shutil.which("codegraph") or "codegraph"

    console.print("Which AI assistant do you want to configure?\n")
    console.print("  [bold]1[/bold]  Claude Code  (project-level .mcp.json)")
    console.print("  [bold]2[/bold]  Claude Desktop  (global ~/.../claude.json)")
    console.print("  [bold]3[/bold]  Gemini CLI  (project-level .gemini/settings.json)")
    console.print("  [bold]4[/bold]  Gemini CLI  (global ~/.gemini/settings.json)")
    console.print("  [bold]5[/bold]  All\n")

    choice = Prompt.ask("Choice", choices=["1", "2", "3", "4", "5"], default="1")

    server_entry = {
        "command": codegraph_exe,
        "args": ["serve", "--config", str(config_path.resolve())],
        "env": {},
    }

    if choice in ("1", "5"):
        _write_project_mcp_json(config_path.parent / ".mcp.json", server_entry)

    if choice in ("2", "5"):
        desktop_path = _claude_desktop_config_paths()[0]
        _write_claude_desktop_json(desktop_path, server_entry)

    if choice in ("3", "5"):
        gemini_project_path = config_path.parent / ".gemini" / "settings.json"
        _write_gemini_settings_json(gemini_project_path, server_entry)

    if choice in ("4", "5"):
        gemini_global_path = _gemini_settings_paths()[0]
        _write_gemini_settings_json(gemini_global_path, server_entry)

    # Verify reachability
    console.print("\n[bold]Verifying server can start...[/bold]")
    try:
        db_manager = _initialize_db(config_path)
        if db_manager.is_connected():
            console.print(
                "   [green]+[/green] Neo4j reachable — server should start correctly"
            )
        else:
            console.print(
                "   [yellow]![/yellow] Neo4j not reachable — server will fail at startup"
            )
            console.print("      Start Neo4j first, then reload your AI assistant.")
    except Exception as e:
        console.print(f"   [yellow]![/yellow] Could not verify: {e}")

    console.print(
        "\n[bold green]Done.[/bold green] Restart your AI assistant to pick up the changes.\n"
    )


def _write_project_mcp_json(mcp_path: Path, server_entry: dict) -> None:
    """Write or update .mcp.json in the project directory."""
    data: dict = {}
    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data.setdefault("mcpServers", {})["codegraph"] = server_entry
    mcp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    console.print(f"   [green]+[/green] Written to {mcp_path}")
    console.print("      Reload Claude Code (or open a new session) to activate.\n")


def _write_claude_desktop_json(desktop_path: Path, server_entry: dict) -> None:
    """Write or update Claude Desktop's claude.json."""
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if desktop_path.exists():
        try:
            data = json.loads(desktop_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data.setdefault("mcpServers", {})["codegraph"] = server_entry
    desktop_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    console.print(f"   [green]+[/green] Written to {desktop_path}")
    console.print("      Restart Claude Desktop to activate.\n")


def _write_gemini_settings_json(path: Path, server_entry: dict) -> None:
    """Write or update Gemini CLI's settings.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data.setdefault("mcpServers", {})["codegraph"] = server_entry
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    console.print(f"   [green]+[/green] Written to {path}")
    console.print("      Reload Gemini CLI (or start a new session) to activate.\n")
