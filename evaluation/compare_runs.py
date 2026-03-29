"""Compare benchmark results across multiple runs.

Usage:
    python evaluation/compare_runs.py <dir1> <dir2> ... [--latex]

Reads summary.json from each directory and prints a Markdown (or LaTeX) table
comparing Recall@5, Recall@10, MRR, and zero-recall instance counts.
"""

import argparse
import json
from pathlib import Path


def load_summary(output_dir: str) -> dict:
    """Load summary.json from an output directory."""
    path = Path(output_dir) / "summary.json"
    if not path.exists():
        raise FileNotFoundError(f"No summary.json in {output_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def _row_label(summary: dict, directory: str) -> str:
    """Derive a display label: retriever name if present, else directory name."""
    retriever = summary.get("retriever", "")
    ablation = summary.get("ablation", "")
    label = retriever or Path(directory).name
    if ablation and ablation != "baseline":
        label = f"{label} ({ablation})"
    return label


def print_markdown(rows: list[tuple[str, dict]]) -> None:
    """Print a Markdown comparison table."""
    header = "| Retriever | Recall@5 | Recall@10 | MRR  | Zero-Recall | N |"
    sep    = "|-----------|----------|-----------|------|-------------|---|"
    print(header)
    print(sep)
    for label, s in rows:
        print(
            f"| {label:<9} "
            f"| {s.get('mean_recall_at_5', 0.0):.4f}   "
            f"| {s.get('mean_recall_at_10', 0.0):.4f}    "
            f"| {s.get('mean_mrr', 0.0):.4f} "
            f"| {s.get('instances_with_zero_recall', 0):<11} "
            f"| {s.get('n_instances', 0)} |"
        )


def print_latex(rows: list[tuple[str, dict]]) -> None:
    """Print a LaTeX booktabs table."""
    print(r"\begin{tabular}{lrrrr}")
    print(r"\toprule")
    print(r"Retriever & Recall@5 & Recall@10 & MRR & Zero-Recall \\")
    print(r"\midrule")
    for label, s in rows:
        print(
            f"{label} & "
            f"{s.get('mean_recall_at_5', 0.0):.4f} & "
            f"{s.get('mean_recall_at_10', 0.0):.4f} & "
            f"{s.get('mean_mrr', 0.0):.4f} & "
            f"{s.get('instances_with_zero_recall', 0)} \\\\"
        )
    print(r"\bottomrule")
    print(r"\end{tabular}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare CodeGraph benchmark runs")
    parser.add_argument("dirs", nargs="+", help="Output directories containing summary.json")
    parser.add_argument("--latex", action="store_true", help="Output LaTeX table instead of Markdown")
    args = parser.parse_args()

    rows: list[tuple[str, dict]] = []
    for d in args.dirs:
        summary = load_summary(d)
        label = _row_label(summary, d)
        rows.append((label, summary))

    if args.latex:
        print_latex(rows)
    else:
        print_markdown(rows)


if __name__ == "__main__":
    main()
