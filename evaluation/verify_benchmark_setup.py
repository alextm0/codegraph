"""Pre-flight checks before SWE-bench ablation sweeps.

Validates harness wiring (run_core_retrieval, config.yaml seeds) and optional
live Neo4j connectivity. Does not run a full benchmark.

Usage:
    python -m evaluation.verify_benchmark_setup
    python -m evaluation.verify_benchmark_setup --live
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from codegraph.utils.config import load_raw_config, parse_signal_weights

from evaluation.ablations import ABLATIONS, PRESETS, resolve_preset


def _check_harness_uses_core_pipeline() -> list[str]:
    """Ensure swe_bench_runner delegates to run_core_retrieval."""
    root = Path(__file__).resolve().parents[1]
    runner_src = (root / "evaluation" / "swe_bench_runner.py").read_text(encoding="utf-8")
    issues: list[str] = []
    if "run_core_retrieval" not in runner_src:
        issues.append("swe_bench_runner.py does not call run_core_retrieval")
    if "file_paths_from_ppr_results" not in runner_src:
        issues.append("swe_bench_runner missing file_paths_from_ppr_results")
    if "_load_benchmark_seed_config" not in runner_src:
        issues.append("swe_bench_runner does not load config.yaml seed_selection")
    if "BenchmarkProgress" not in runner_src:
        issues.append("swe_bench_runner missing BenchmarkProgress reporting")
    return issues


def _check_config_seed_section(config_path: str) -> list[str]:
    """Report seed_selection keys loaded from config."""
    issues: list[str] = []
    raw = load_raw_config(config_path)
    seed = raw.get("seed_selection") or {}
    weights = parse_signal_weights(seed)
    if not weights:
        issues.append(
            "config.yaml has no seed_selection weights (using code defaults only)"
        )
    exclude = seed.get("exclude_seed_paths")
    if not exclude:
        issues.append("config.yaml has no exclude_seed_paths")
    return issues


def _check_ablations_registered() -> list[str]:
    """Every preset name must exist in ABLATIONS."""
    issues: list[str] = []
    names = {a.name for a in ABLATIONS}
    for preset, ablation_list in PRESETS.items():
        for ab in ablation_list:
            if ab not in names:
                issues.append(f"preset '{preset}' references unknown ablation '{ab}'")
    return issues


def _check_live_neo4j(config_path: str) -> list[str]:
    """Verify Neo4j + GDS if --live."""
    issues: list[str] = []
    try:
        from codegraph.core.graph.connection import (
            create_driver,
            load_config,
            verify_connectivity,
        )
        from codegraph.core.graph.ppr import create_gds_client

        cfg = load_config(config_path)
        driver = create_driver(cfg)
        try:
            verify_connectivity(driver)
            create_gds_client(driver)
        finally:
            driver.close()
    except Exception as exc:
        issues.append(f"Neo4j/GDS not ready: {exc}")
    return issues


def run_checks(*, config_path: str, live: bool) -> int:
    """Run all checks; return process exit code (0 = ok)."""
    failures: list[str] = []
    failures.extend(_check_harness_uses_core_pipeline())
    failures.extend(_check_config_seed_section(config_path))
    failures.extend(_check_ablations_registered())

    # Ensure sweep module importable
    try:
        importlib.import_module("evaluation.run_ablation_sweep")
    except ImportError as exc:
        failures.append(f"cannot import run_ablation_sweep: {exc}")

    if live:
        failures.extend(_check_live_neo4j(config_path))

    print("Benchmark harness verification")
    print(f"  config: {config_path}")
    print(f"  ablations registered: {len(ABLATIONS)}")
    print(f"  presets: {', '.join(sorted(PRESETS.keys()))}")
    print(f"  quick preset: {resolve_preset('quick')}")

    raw = load_raw_config(config_path)
    seed = raw.get("seed_selection") or {}
    print(f"  seed weights from config: {parse_signal_weights(seed)}")
    print(f"  exclude_seed_paths: {seed.get('exclude_seed_paths')}")

    if failures:
        print("\nFAILED:")
        for msg in failures:
            print(f"  - {msg}")
        return 1

    print("\nOK — harness wiring looks correct.")
    if not live:
        print("  (Run with --live to verify Neo4j connectivity)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SWE-bench harness setup")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also check Neo4j + GDS connectivity",
    )
    args = parser.parse_args()
    sys.exit(run_checks(config_path=args.config, live=args.live))


if __name__ == "__main__":
    main()
