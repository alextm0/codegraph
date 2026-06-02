"""Query command helper."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from codegraph.core.graph import get_database_manager, load_full_config
from codegraph.utils.config import parse_signal_weights, resolve_project_root
from codegraph.utils.logging import setup_logging

from codegraph.cli.commands._shared import console, logger


def query_helper(
    config_path: Path,
    task: str,
    entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
    json_out: bool = False,
    compact: bool = False,
    trace: bool = False,
) -> None:
    """Run the retrieval pipeline and print context to stdout."""
    setup_logging(level=logging.WARNING)

    raw_config = load_full_config(config_path)
    project_root_str = str(resolve_project_root(raw_config, config_path))

    from codegraph.core.graph.ppr import PPRConfig, create_gds_client
    from codegraph.core.retrieval.pipeline import run_core_retrieval, run_retrieval_pipeline
    from codegraph.core.retrieval.trace import build_retrieval_trace

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
            if trace:
                core = run_core_retrieval(
                    driver=driver,
                    gds=gds,
                    task_description=task,
                    mentioned_entities=entities,
                    current_file=current_file,
                    ppr_config=ppr_config,
                    signal_weights=signal_weights or None,
                    exclude_seed_paths=exclude_seed_paths or None,
                )
                if not core:
                    console.print(
                        "[yellow]No results found. Is the graph built? Run: codegraph rebuild[/yellow]"
                    )
                    return
                trace_data = build_retrieval_trace(
                    driver, core, ppr_config, task, top_k=ppr_config.top_k
                )
                console.print(json.dumps(trace_data, indent=2))
                from codegraph.core.retrieval.post_processing import format_context

                results = format_context(
                    core.ppr_results, project_root_str, effective_budget
                )
            else:
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
                console.print(json.dumps({"results": [], "total": 0}))
            else:
                console.print(
                    "[yellow]No results found. Is the graph built? Run: codegraph rebuild[/yellow]"
                )
            return

        if json_out:
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
