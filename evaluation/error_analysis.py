"""Categorize zero-recall instances from a benchmark per_instance.jsonl file.

Helps understand the root causes of retrieval failures to guide improvements.
Usage: python -m evaluation.error_analysis evaluation/results/ppr_uniform/per_instance.jsonl
"""

import json
import sys
from pathlib import Path
from collections import Counter


_CATEGORY_NO_SEEDS = "no_seeds"
_CATEGORY_NEAR_MISS = "near_miss"       # gold found but rank > 10
_CATEGORY_WRONG_DIR = "wrong_directory"  # seeds in different dir than gold
_CATEGORY_SETUP_ERROR = "setup_error"
_CATEGORY_UNKNOWN = "unknown"


def categorize_instance(result: dict) -> str:
    """Assign a failure category to a zero-recall instance.

    Categories:
    - no_seeds: n_seeds == 0 (seed selection completely failed)
    - near_miss: gold file found in predictions but beyond rank 10
    - wrong_directory: seed files are in a different top-level directory than gold
    - setup_error: an exception occurred during processing
    - unknown: seeds exist, no error, gold not found anywhere in predictions

    Args:
        result: One row from per_instance.jsonl (already a dict).

    Returns:
        One of the category string constants.
    """
    if result.get("error"):
        return _CATEGORY_SETUP_ERROR

    if result.get("n_seeds", 0) == 0:
        return _CATEGORY_NO_SEEDS

    gold_files = set(result.get("gold_files") or [])
    predicted_files = result.get("predicted_files") or []

    # Check if gold is a near miss (found but beyond rank 10)
    for gold in gold_files:
        if gold in predicted_files:
            return _CATEGORY_NEAR_MISS

    # Check if seed files are in a different directory than gold files
    seed_files = result.get("seed_files") or []
    if seed_files and gold_files:
        seed_dirs = {_top_dir(f) for f in seed_files if f}
        gold_dirs = {_top_dir(f) for f in gold_files if f}
        if not seed_dirs & gold_dirs:  # no directory overlap
            return _CATEGORY_WRONG_DIR

    return _CATEGORY_UNKNOWN


def _top_dir(file_path: str) -> str:
    """Return the top-level directory of a file path (first path segment)."""
    parts = file_path.replace("\\", "/").split("/")
    return parts[0] if parts else ""


def analyze(jsonl_path: str) -> dict:
    """Read per_instance.jsonl and return a categorized summary of failures.

    Args:
        jsonl_path: Path to the per_instance.jsonl file.

    Returns:
        Dict with keys: total, zero_recall, categories (Counter), examples (dict).
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {jsonl_path}")

    all_results: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                all_results.append(json.loads(line))

    zero_recall = [r for r in all_results if r.get("recall_at_10", 0) == 0.0]
    categories: Counter = Counter()
    examples: dict[str, list[dict]] = {
        _CATEGORY_NO_SEEDS: [],
        _CATEGORY_NEAR_MISS: [],
        _CATEGORY_WRONG_DIR: [],
        _CATEGORY_SETUP_ERROR: [],
        _CATEGORY_UNKNOWN: [],
    }

    for result in zero_recall:
        cat = categorize_instance(result)
        categories[cat] += 1
        # Keep up to 3 examples per category for display
        if len(examples[cat]) < 3:
            examples[cat].append(result)

    return {
        "total": len(all_results),
        "zero_recall": len(zero_recall),
        "categories": categories,
        "examples": examples,
    }


def print_report(summary: dict) -> None:
    """Print a human-readable analysis report to stdout."""
    total = summary["total"]
    zero = summary["zero_recall"]
    categories = summary["categories"]
    examples = summary["examples"]

    print(f"\n{'='*60}")
    print(f"Error Analysis Report")
    print(f"{'='*60}")
    print(f"Total instances:   {total}")
    print(f"Zero-recall:       {zero} ({100*zero/total:.1f}%)")
    print(f"\nFailure categories (of {zero} zero-recall instances):")

    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        pct = 100 * count / zero if zero else 0
        print(f"  {cat:<25} {count:>4} ({pct:.1f}%)")

    print(f"\nExample instances per category:")
    for cat, inst_list in examples.items():
        if not inst_list:
            continue
        print(f"\n  [{cat}]")
        for inst in inst_list:
            gold = inst.get("gold_files", [])
            predicted = (inst.get("predicted_files") or [])[:3]
            seeds = inst.get("n_seeds", "?")
            print(f"    {inst['instance_id']}")
            print(f"      gold:      {gold}")
            print(f"      top-3 pred: {predicted}")
            print(f"      n_seeds:   {seeds}")


def main() -> None:
    """Entry point: python -m evaluation.error_analysis <jsonl_path>"""
    if len(sys.argv) < 2:
        print("Usage: python -m evaluation.error_analysis <per_instance.jsonl>", file=sys.stderr)
        sys.exit(1)

    summary = analyze(sys.argv[1])
    print_report(summary)


if __name__ == "__main__":
    main()
