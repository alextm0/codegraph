"""Explain command helper."""

from __future__ import annotations

import logging
from pathlib import Path

from rich import box
from rich.table import Table

from codegraph.core.graph.ppr import PPRConfig, create_gds_client
from codegraph.core.retrieval.explanations import build_explained_results
from codegraph.core.retrieval.pipeline import run_core_retrieval
from codegraph.utils.config import load_raw_config, parse_signal_weights
from codegraph.utils.graph_helpers import fetch_seed_names
from codegraph.utils.logging import setup_logging

from codegraph.cli.commands._shared import _initialize_db, console


def explain_helper(
    config_path: Path, task: str, top_k: int = 10, trace: bool = False
) -> None:
    """Show seeds, PPR scores, and graph paths explaining why each file was returned."""
    setup_logging(level=logging.WARNING)

    raw_config = load_raw_config(config_path)
    seed_section = raw_config.get("seed_selection", {})
    signal_weights = parse_signal_weights(seed_section)
    exclude_seed_paths = seed_section.get("exclude_seed_paths") or None

    db_manager = _initialize_db(config_path)
    driver = db_manager.get_driver()

    if not db_manager.is_connected():
        console.print("[bold red]ERROR:[/bold red] Cannot reach Neo4j.")
        return

    console.print(f'\nExplaining: [bold cyan]"{task}"[/bold cyan]\n')

    ppr_section = raw_config.get("ppr", {})
    ppr_config = PPRConfig(
        damping_factor=ppr_section.get("damping_factor", 0.70),
        max_iterations=ppr_section.get("max_iterations", 20),
        tolerance=ppr_section.get("tolerance", 1e-7),
        top_k=ppr_section.get("top_k", 30),
    )
    gds = create_gds_client(driver)
    core_result = run_core_retrieval(
        driver=driver,
        gds=gds,
        task_description=task,
        ppr_config=ppr_config,
        signal_weights=signal_weights,
        exclude_seed_paths=exclude_seed_paths,
    )
    if not core_result:
        console.print(
            "[yellow]No seeds found. Is the graph built? Run: codegraph rebuild[/yellow]"
        )
        return

    seed_ids = list(core_result.seeds.seeds.keys())
    seed_names = fetch_seed_names(driver, seed_ids)
    _print_seeds_table(core_result.seeds, seed_names)

    if trace:
        import json
        from codegraph.core.retrieval.trace import build_retrieval_trace

        trace_data = build_retrieval_trace(
            driver, core_result, ppr_config, task, top_k=top_k
        )
        console.print(json.dumps(trace_data, indent=2))
        return

    explained = build_explained_results(
        driver, core_result, top_k=top_k, dedupe_by="file"
    )
    _print_explained_table(explained)


def _print_seeds_table(seeds, seed_names: dict[int, str]) -> None:
    """Print the seeds summary table to the console."""
    seeds_table = Table(
        title=f"Seeds ({len(seeds.seeds)} nodes)", box=box.SIMPLE_HEAVY
    )
    seeds_table.add_column("Seed node", style="cyan")
    seeds_table.add_column("Signal", style="magenta")
    seeds_table.add_column("Weight", justify="right", style="green")

    for nid, weight in sorted(seeds.seeds.items(), key=lambda x: -x[1]):
        name = seed_names.get(nid, str(nid))
        source = seeds.metadata.get(nid, {}).get("source", "unknown")
        seeds_table.add_row(name, source, f"{weight:.3f}")
    console.print(seeds_table)


def _print_explained_table(explained) -> None:
    """Print the top results table with reasoning paths."""
    results_table = Table(
        title="Top Results — Why did PPR return these?", box=box.SIMPLE_HEAVY
    )
    results_table.add_column("#", justify="right", style="bold")
    results_table.add_column("File", style="blue")
    results_table.add_column("Score", justify="right", style="green")
    results_table.add_column("Contribution", style="magenta")
    results_table.add_column("Reasoning path from nearest seed", style="dim")

    for item in explained:
        results_table.add_row(
            str(item.rank),
            item.file_path,
            f"{item.ppr_score:.5f}",
            item.contribution,
            item.reasoning_path,
        )

    console.print(results_table)
    console.print()
