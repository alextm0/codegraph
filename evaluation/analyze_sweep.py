"""Analyze an ablation sweep directory.

Usage:
    python -m evaluation.analyze_sweep evaluation/results/ablation_sweep
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from evaluation.compare_runs import load_summary, print_markdown


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def analyze_run(run_dir: Path) -> dict:
    """Per-run stats beyond summary.json."""
    summary = load_summary(str(run_dir))
    instances = _load_jsonl(run_dir / "per_instance.jsonl")
    errors = sum(1 for r in instances if r.get("error"))
    no_seeds = sum(1 for r in instances if not r.get("error") and r.get("n_seeds", 0) == 0)
    hits = sum(1 for r in instances if r.get("recall_at_10", 0) > 0)
    by_repo: dict[str, list[float]] = defaultdict(list)
    for r in instances:
        if r.get("error"):
            continue
        repo = (r.get("repo") or "unknown").split("/")[0]
        by_repo[repo].append(float(r.get("recall_at_10", 0)))

    repo_r10 = {
        repo: sum(v) / len(v) if v else 0.0 for repo, v in sorted(by_repo.items())
    }
    return {
        "summary": summary,
        "n_jsonl": len(instances),
        "errors": errors,
        "no_seeds": no_seeds,
        "hits_at_10": hits,
        "hit_rate": hits / len(instances) if instances else 0.0,
        "repo_recall_at_10": repo_r10,
    }


def analyze_sweep_root(root: Path) -> None:
    """Print comparison and per-run diagnostics."""
    sweep_path = root / "sweep_summary.json"
    if sweep_path.exists():
        sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
        print("=== sweep_summary.json (best) ===")
        print(json.dumps(sweep.get("best"), indent=2))
        print()

    run_dirs = sorted(
        p for p in root.iterdir()
        if p.is_dir() and (p / "summary.json").exists()
    )
    if not run_dirs:
        print(f"No completed runs under {root}")
        return

    rows: list[tuple[str, dict]] = []
    for run_dir in run_dirs:
        summary = load_summary(str(run_dir))
        rows.append((run_dir.name, summary))

    print("=== Comparison (summary.json) ===")
    print_markdown(rows)
    print()

    for run_dir in run_dirs:
        stats = analyze_run(run_dir)
        s = stats["summary"]
        print(f"--- {run_dir.name} ---")
        print(
            f"  R@10={s.get('mean_recall_at_10', 0):.4f}  "
            f"R@5={s.get('mean_recall_at_5', 0):.4f}  "
            f"MRR={s.get('mean_mrr', 0):.4f}  "
            f"zero={s.get('instances_with_zero_recall', 0)}  "
            f"errors={stats['errors']}  no_seeds={stats['no_seeds']}"
        )
        if stats["repo_recall_at_10"]:
            worst = min(stats["repo_recall_at_10"].items(), key=lambda x: x[1])
            best = max(stats["repo_recall_at_10"].items(), key=lambda x: x[1])
            print(f"  repo R@10 worst: {worst[0]}={worst[1]:.2f}  best: {best[0]}={best[1]:.2f}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze ablation sweep results")
    parser.add_argument("sweep_root", help="Directory containing ablation subfolders")
    parser.add_argument(
        "--compare-baseline",
        default=None,
        help="Print delta vs this summary.json path",
    )
    args = parser.parse_args()
    analyze_sweep_root(Path(args.sweep_root))
    if args.compare_baseline:
        ref_path = Path(args.compare_baseline)
        if ref_path.exists():
            ref = json.loads(ref_path.read_text(encoding="utf-8"))
            print("\n=== vs baseline reference ===")
            print(
                f"  reference R@10={ref.get('mean_recall_at_10', 0):.4f} "
                f"zero={ref.get('instances_with_zero_recall', 0)} "
                f"n={ref.get('n_instances', 0)}"
            )


if __name__ == "__main__":
    main()
