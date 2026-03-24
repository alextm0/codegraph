"""Categorize zero-recall instances from a benchmark per_instance.jsonl file.

Helps understand root causes of retrieval failures to guide improvements.

Usage:
    python -m evaluation.error_analysis evaluation/results/ppr_uniform/per_instance.jsonl
"""

import json
import sys
from collections import Counter
from pathlib import Path


# Failure category constants
_NO_SEEDS = "no_seeds"          # seed selection returned nothing
_NEAR_MISS = "near_miss"        # gold found in predictions but at rank > 10
_WRONG_DIR = "wrong_directory"  # seeds are in a completely different directory
_SETUP_ERROR = "setup_error"    # an exception occurred during processing
_UNKNOWN = "unknown"            # seeds exist but gold not found anywhere


def categorize_instance(result: dict) -> str:
    """Assign a failure category to a zero-recall instance.

    Args:
        result: One parsed row from per_instance.jsonl.

    Returns:
        One of the category string constants (_NO_SEEDS, _NEAR_MISS, etc.).
    """
    if result.get("error"):
        return _SETUP_ERROR

    if result.get("n_seeds", 0) == 0:
        return _NO_SEEDS

    gold_files = set(result.get("gold_files") or [])
    predicted_files = result.get("predicted_files") or []

    # Near miss: gold is in predictions but ranked beyond top 10
    for gold in gold_files:
        if gold in predicted_files:
            return _NEAR_MISS

    # Wrong directory: seeds came from different top-level dirs than gold
    seed_files = result.get("seed_files") or []
    if seed_files and gold_files:
        seed_dirs = {_top_dir(f) for f in seed_files if f}
        gold_dirs = {_top_dir(f) for f in gold_files if f}
        if not (seed_dirs & gold_dirs):
            return _WRONG_DIR

    return _UNKNOWN


def _top_dir(file_path: str) -> str:
    """Return the top-level directory (first path segment) of a file path."""
    parts = file_path.replace("\\", "/").split("/")
    return parts[0] if parts else ""


def analyze(jsonl_path: str) -> dict:
    """Read per_instance.jsonl and return a categorized summary of failures.

    Args:
        jsonl_path: Path to the per_instance.jsonl file.

    Returns:
        Dict with keys: total, zero_recall_count, categories (Counter),
        examples (dict mapping category -> list of up to 3 example instances).
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Not found: {jsonl_path}")

    all_results: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_results.append(json.loads(line))

    zero_recall = [r for r in all_results if r.get("recall_at_10", 0) == 0.0]
    categories: Counter = Counter()
    examples: dict[str, list[dict]] = {
        _NO_SEEDS: [], _NEAR_MISS: [], _WRONG_DIR: [],
        _SETUP_ERROR: [], _UNKNOWN: [],
    }

    for result in zero_recall:
        cat = categorize_instance(result)
        categories[cat] += 1
        if len(examples[cat]) < 3:
            examples[cat].append(result)

    return {
        "total": len(all_results),
        "zero_recall_count": len(zero_recall),
        "categories": categories,
        "examples": examples,
    }


def print_report(summary: dict) -> None:
    """Print a human-readable analysis report to stdout.

    Args:
        summary: Output from analyze().
    """
    total = summary["total"]
    zero = summary["zero_recall_count"]
    categories = summary["categories"]
    examples = summary["examples"]

    print(f"\n{'='*60}")
    print("Error Analysis Report")
    print(f"{'='*60}")
    print(f"Total instances:  {total}")
    print(f"Zero-recall:      {zero} ({100*zero/total:.1f}%)")
    print(f"\nFailure categories ({zero} zero-recall instances):")

    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        pct = 100 * count / zero if zero else 0
        print(f"  {cat:<25} {count:>4}  ({pct:.1f}%)")

    print("\nExamples per category (up to 3 each):")
    for cat, inst_list in examples.items():
        if not inst_list:
            continue
        print(f"\n  [{cat}]")
        for inst in inst_list:
            gold = inst.get("gold_files", [])
            predicted = (inst.get("predicted_files") or [])[:3]
            n_seeds = inst.get("n_seeds", "?")
            seed_files = (inst.get("seed_files") or [])[:2]
            print(f"    {inst['instance_id']}")
            print(f"      gold:        {gold}")
            print(f"      top-3 pred:  {predicted}")
            print(f"      n_seeds:     {n_seeds}  seed_files: {seed_files}")


def main() -> None:
    """CLI entry point: python -m evaluation.error_analysis <per_instance.jsonl>"""
    if len(sys.argv) < 2:
        print(
            "Usage: python -m evaluation.error_analysis <per_instance.jsonl>",
            file=sys.stderr,
        )
        sys.exit(1)

    summary = analyze(sys.argv[1])
    print_report(summary)


if __name__ == "__main__":
    main()
