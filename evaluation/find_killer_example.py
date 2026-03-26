"""
Find SWE-bench instances where CodeGraph (PPR) retrieves the gold file
but BM25 misses it entirely. Useful for identifying thesis "killer example" cases.

Usage:
    python evaluation/find_killer_example.py
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
PPR_RUN = RESULTS_DIR / "iteration_2_full" / "per_instance.jsonl"
BM25_RUN = RESULTS_DIR / "iteration_1_bm25_baseline" / "per_instance.jsonl"

TOP_N = 5


def load_results(path: Path) -> dict[str, dict]:
    """Load a per_instance.jsonl file indexed by instance_id."""
    results: dict[str, dict] = {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            results[record["instance_id"]] = record
    return results


def find_wins(
    ppr: dict[str, dict],
    bm25: dict[str, dict],
) -> list[dict]:
    """Return instances where PPR recall@10=1.0 but BM25 recall@10=0.0."""
    wins = []
    for instance_id, ppr_rec in ppr.items():
        if instance_id not in bm25:
            continue
        bm25_rec = bm25[instance_id]

        ppr_recall = ppr_rec.get("recall_at_10", 0.0)
        bm25_recall = bm25_rec.get("recall_at_10", 0.0)

        if ppr_recall == 1.0 and bm25_recall == 0.0:
            wins.append(
                {
                    "instance_id": instance_id,
                    "repo": ppr_rec.get("repo", ""),
                    "gold_files": ppr_rec.get("gold_files", []),
                    "ppr_predicted": ppr_rec.get("predicted_files", []),
                    "bm25_predicted": bm25_rec.get("predicted_files", [])[:10],
                    "ppr_mrr": ppr_rec.get("mrr", 0.0),
                    "ppr_recall_5": ppr_rec.get("recall_at_5", 0.0),
                    "n_seeds": ppr_rec.get("n_seeds", 0),
                    "seed_files": ppr_rec.get("seed_files", []),
                }
            )

    # Sort by MRR descending (highest-ranked gold file first)
    wins.sort(key=lambda x: x["ppr_mrr"], reverse=True)
    return wins


def _gold_rank(predicted: list[str], gold_files: list[str]) -> int | None:
    """Return 1-based rank of first gold file in predicted list, or None."""
    for i, f in enumerate(predicted):
        if f in gold_files:
            return i + 1
    return None


def print_summary(wins: list[dict], n: int = TOP_N) -> None:
    """Print a human-readable summary of the top N wins."""
    total = len(wins)
    print(f"\n{'='*70}")
    print(f"CodeGraph wins (PPR recall@10=1, BM25 recall@10=0): {total} instances")
    print(f"{'='*70}\n")

    for i, w in enumerate(wins[:n], 1):
        rank = _gold_rank(w["ppr_predicted"], w["gold_files"])
        print(f"-- #{i} {w['instance_id']}")
        print(f"   repo       : {w['repo']}")
        print(f"   gold files : {w['gold_files']}")
        print(f"   PPR rank   : #{rank} of {len(w['ppr_predicted'])} (MRR={w['ppr_mrr']:.3f}, R@5={w['ppr_recall_5']:.1f})")
        print(f"   n_seeds    : {w['n_seeds']}  seed_files: {w['seed_files'][:3]}")
        print(f"   BM25 top-10: {w['bm25_predicted'][:5]}...")
        print()

    if wins:
        best = wins[0]
        rank = _gold_rank(best["ppr_predicted"], best["gold_files"])
        print("=" * 70)
        print("RECOMMENDED KILLER EXAMPLE (highest MRR win):")
        print(f"  Instance  : {best['instance_id']}")
        print(f"  Gold file : {best['gold_files']}")
        print(f"  PPR rank  : #{rank}  (MRR={best['ppr_mrr']:.3f})")
        print(f"\nNext step: run `codegraph explain \"<task description from SWE-bench>\"` on this instance")
        print(f"to generate the graph path walkthrough for docs/thesis/killer-example.md")
        print(f"{'='*70}\n")


def main() -> None:
    """Entry point."""
    print(f"Loading PPR results from  : {PPR_RUN}")
    print(f"Loading BM25 results from : {BM25_RUN}")

    ppr = load_results(PPR_RUN)
    bm25 = load_results(BM25_RUN)

    print(f"Loaded {len(ppr)} PPR instances, {len(bm25)} BM25 instances")

    wins = find_wins(ppr, bm25)
    print_summary(wins)


if __name__ == "__main__":
    main()
