"""Main CLI implementation."""

import argparse
import logging
import sys
from pathlib import Path

from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.logging import setup_logging
from codegraph.utils.ignore import load_ignore_patterns
from codegraph.core.graph import create_driver, load_config, load_full_config, clear_database, build_graph
from codegraph.core.graph.connection import verify_connectivity
from codegraph.core.graph.queries import count_nodes_by_label, count_edges_by_type, get_most_connected_files
from codegraph.core.parser import create_parser, parse_directory

logger = logging.getLogger(__name__)


def cli() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CodeGraph — graph-based code context engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # rebuild command
    subparsers.add_parser("rebuild", help="Clear and rebuild the code graph")

    # serve command
    serve_p = subparsers.add_parser("serve", help="Start the MCP server")
    serve_p.add_argument("--config", type=str, default=None, dest="serve_config",
                         help="Config path passed to the MCP server")

    # stats command
    subparsers.add_parser("stats", help="Show node and edge counts for the current graph")

    # doctor command
    subparsers.add_parser("doctor", help="Check Neo4j connectivity, GDS, and config health")

    # query command
    query_p = subparsers.add_parser("query", help="Run retrieval pipeline from the terminal")
    query_p.add_argument("task", type=str, help="Task description to retrieve context for")
    query_p.add_argument("--entities", nargs="*", default=None,
                         help="Specific entity names to include as seeds")
    query_p.add_argument("--file", type=str, default=None,
                         help="Current file path (used as a low-weight seed hint)")
    query_p.add_argument("--top-k", type=int, default=0,
                         help="Max results (0 = use config default)")
    query_p.add_argument("--budget", type=int, default=0,
                         help="Token budget (0 = use config default)")

    args = parser.parse_args()

    # Resolve config path
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        config_path = Path(__file__).parent.parent.parent.parent / "config.yaml"

    if args.command == "rebuild":
        cmd_rebuild(config_path)
    elif args.command == "serve":
        cmd_serve(getattr(args, "serve_config", None) or str(config_path))
    elif args.command == "stats":
        cmd_stats(config_path)
    elif args.command == "doctor":
        cmd_doctor(config_path)
    elif args.command == "query":
        cmd_query(config_path, args.task, args.entities, args.file, args.top_k, args.budget)
    else:
        parser.print_help()


def cmd_rebuild(config_path: Path) -> None:
    """Rebuild the graph with progress output."""
    setup_logging()

    raw_config = load_raw_config(config_path)
    project_root = resolve_project_root(raw_config, config_path)

    neo4j_config = load_config(config_path)
    driver = create_driver(neo4j_config)

    try:
        print(f"Connecting to Neo4j at {neo4j_config.uri}...")
        if not verify_connectivity(driver):
            print("ERROR: Cannot reach Neo4j. Is it running?", file=sys.stderr)
            sys.exit(1)
        print("Connected.")

        print("Clearing existing graph...")
        deleted = clear_database(driver)
        print(f"  Cleared {deleted} nodes.")

        # Load ignore patterns
        ignore_file = project_root / ".cgignore"
        exclude = raw_config.get("parser", {}).get("exclude_patterns", [])
        exclude += raw_config.get("exclude_patterns", [])
        if ignore_file.exists():
            print(f"  Loading ignore patterns from {ignore_file.name}")
            exclude.extend(load_ignore_patterns(ignore_file))

        print(f"Parsing: {project_root}")
        parser = create_parser()
        parsed_count = [0]

        def parse_progress(current: int, total: int, file_path: str) -> None:
            parsed_count[0] = current
            # Print a compact progress line, overwriting in-place
            short = Path(file_path).name
            print(f"\r  [{current}/{total}] {short:<40}", end="", flush=True)

        all_entities = parse_directory(
            str(project_root), parser, exclude_patterns=exclude,
            progress_callback=parse_progress,
        )
        print(f"\r  Parsed {len(all_entities)} files.{' ' * 50}")

        print("Building graph...")
        def graph_progress(stage: str, count: int) -> None:
            print(f"  {stage}: {count}")

        counts = build_graph(driver, all_entities, progress_callback=graph_progress)

        total_nodes = sum(v for k, v in counts.items() if k in ("File", "Function", "Class", "Method"))
        total_edges = sum(v for k, v in counts.items() if k in ("CONTAINS", "CALLS", "IMPORTS", "INHERITS_FROM"))
        print(f"\nGraph rebuild complete: {total_nodes} nodes, {total_edges} edges.")
    finally:
        driver.close()


def cmd_serve(config_path_str: str) -> None:
    """Start MCP server, passing through the config path."""
    import os
    os.environ["CODEGRAPH_CONFIG"] = str(Path(config_path_str).resolve())
    from codegraph.mcp.server import main as serve_main
    serve_main()


def cmd_stats(config_path: Path) -> None:
    """Show node and edge counts."""
    setup_logging(level=logging.WARNING)

    neo4j_config = load_config(config_path)
    driver = create_driver(neo4j_config)
    try:
        if not verify_connectivity(driver):
            print("ERROR: Cannot reach Neo4j.", file=sys.stderr)
            sys.exit(1)

        node_counts = count_nodes_by_label(driver)
        edge_counts = count_edges_by_type(driver)
        most_connected = get_most_connected_files(driver, limit=5)

        print("\n=== Graph Statistics ===\n")
        print("Nodes:")
        total_nodes = 0
        for label, cnt in sorted(node_counts.items()):
            print(f"  {label:<15} {cnt:>6}")
            total_nodes += cnt
        print(f"  {'TOTAL':<15} {total_nodes:>6}")

        print("\nEdges:")
        total_edges = 0
        for rel_type, cnt in sorted(edge_counts.items()):
            print(f"  {rel_type:<15} {cnt:>6}")
            total_edges += cnt
        print(f"  {'TOTAL':<15} {total_edges:>6}")

        if most_connected:
            print("\nTop files by entity count:")
            for row in most_connected:
                print(f"  {row['entity_count']:>4}  {row['file_path']}")
        print()
    finally:
        driver.close()


def cmd_doctor(config_path: Path) -> None:
    """Run health checks on Neo4j, GDS, and config."""
    setup_logging(level=logging.WARNING)
    ok = True

    # 1. Config file
    print(f"[1/4] Config file: {config_path}")
    if config_path.exists():
        print("      OK")
    else:
        print("      FAIL — file not found")
        ok = False

    # 2. Neo4j connectivity
    print("[2/4] Neo4j connectivity")
    try:
        neo4j_config = load_config(config_path)
        driver = create_driver(neo4j_config)
        connected = verify_connectivity(driver)
    except Exception as exc:
        print(f"      FAIL — {exc}")
        ok = False
        driver = None
        connected = False

    if connected:
        print(f"      OK ({neo4j_config.uri})")
    elif driver is not None:
        print(f"      FAIL — cannot reach {neo4j_config.uri}")
        ok = False

    # 3. GDS plugin
    print("[3/4] GDS plugin")
    if connected and driver:
        try:
            from codegraph.core.graph.ppr import create_gds_client
            gds = create_gds_client(driver)
            version_df = gds.version()
            # version_df may be a string or dict depending on graphdatascience version
            print(f"      OK (version: {version_df})")
        except Exception as exc:
            print(f"      FAIL — {exc}")
            ok = False
        finally:
            driver.close()
    else:
        print("      SKIP (Neo4j not reachable)")

    # 4. Project root
    print("[4/4] Project root")
    try:
        raw_config = load_raw_config(config_path)
        project_root = resolve_project_root(raw_config, config_path)
        if project_root.exists():
            py_count = len(list(project_root.rglob("*.py")))
            print(f"      OK ({project_root}) — {py_count} .py files found")
        else:
            print(f"      FAIL — directory not found: {project_root}")
            ok = False
    except Exception as exc:
        print(f"      FAIL — {exc}")
        ok = False

    print()
    if ok:
        print("All checks passed.")
    else:
        print("Some checks failed. See above.")
        sys.exit(1)


def cmd_query(
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

    neo4j_config = load_config(config_path)
    driver = create_driver(neo4j_config)
    try:
        if not verify_connectivity(driver):
            print("ERROR: Cannot reach Neo4j.", file=sys.stderr)
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

        signal_weights: dict[str, float] = {}
        if seed_section.get("entity_match_weight") is not None:
            signal_weights["entity_match"] = float(seed_section["entity_match_weight"])
        if seed_section.get("bm25_weight") is not None:
            signal_weights["bm25"] = float(seed_section["bm25_weight"])
        if seed_section.get("current_file_weight") is not None:
            signal_weights["current_file"] = float(seed_section["current_file_weight"])
        if seed_section.get("bm25_top_n") is not None:
            signal_weights["bm25_top_n"] = float(seed_section["bm25_top_n"])

        gds = create_gds_client(driver)

        print(f"Running retrieval for: {task!r}")
        if entities:
            print(f"  Seed entities: {entities}")
        if current_file:
            print(f"  Current file:  {current_file}")
        print()

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
        )

        if not results:
            print("No results found. Is the graph built? Run: codegraph rebuild")
            return

        print(f"Found {len(results)} context items:\n")
        for i, item in enumerate(results, start=1):
            print(f"--- [{i}] {item.qualified_name} (score={item.relevance_score:.4f}, {item.token_count} tokens) ---")
            print(f"    File: {item.file_path}:{item.line_start}-{item.line_end}")
            print()
            # Print first 20 lines of source
            lines = item.source_code.splitlines()
            preview = lines[:20]
            for line in preview:
                print(f"    {line}")
            if len(lines) > 20:
                print(f"    ... ({len(lines) - 20} more lines)")
            print()
    finally:
        driver.close()


if __name__ == "__main__":
    cli()
