"""JSONL and summary I/O for SWE-bench benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from evaluation.metrics import aggregate_metrics, per_repo_recall_at_10


def flush_ordered(
    buffer: dict[int, dict],
    next_idx: int,
    fh: TextIO,
    force_all: bool = False,
) -> int:
    """Write contiguous results from buffer to JSONL in dataset order.

    Returns the updated next_idx.
    """
    if force_all:
        for idx in sorted(buffer.keys()):
            fh.write(json.dumps(buffer[idx]) + "\n")
        fh.flush()
        buffer.clear()
        return next_idx

    while next_idx in buffer:
        fh.write(json.dumps(buffer.pop(next_idx)) + "\n")
        next_idx += 1
    fh.flush()
    return next_idx


class ReportWriter:
    """Manage per_instance.jsonl and summary.json for a benchmark run."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.per_instance_path = output_dir / "per_instance.jsonl"
        self.summary_path = output_dir / "summary.json"

    def load_resume_state(
        self,
        resume: bool,
        retry_errors: bool,
    ) -> tuple[set[str], set[str]]:
        """Return (completed_ids, errored_ids) from an existing JSONL file."""
        completed_ids: set[str] = set()
        errored_ids: set[str] = set()
        if not resume or not self.per_instance_path.exists():
            return completed_ids, errored_ids

        with open(self.per_instance_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    iid = rec["instance_id"]
                    if rec.get("error"):
                        errored_ids.add(iid)
                    else:
                        completed_ids.add(iid)
                except (json.JSONDecodeError, KeyError):
                    pass

        if retry_errors and errored_ids:
            self._remove_errored_lines(errored_ids)
        else:
            completed_ids |= errored_ids

        return completed_ids, errored_ids

    def open_jsonl(self, append: bool) -> TextIO:
        """Open per_instance.jsonl for writing."""
        mode = "a" if append else "w"
        return open(self.per_instance_path, mode, encoding="utf-8")

    def read_all_results(self) -> list[dict]:
        """Read every result line from per_instance.jsonl."""
        if not self.per_instance_path.exists():
            return []
        results: list[dict] = []
        with open(self.per_instance_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return results

    def write_summary(
        self,
        all_results: list[dict],
        ablation_name: str,
        retriever: str,
        grouping: dict,
        git_commit: str | None = None,
        *,
        subset_name: str | None = None,
        compare_baseline: dict | None = None,
    ) -> dict:
        """Write summary.json and return the summary dict."""
        summary = aggregate_metrics(all_results)
        summary["ablation"] = ablation_name
        summary["retriever"] = retriever
        summary["grouping"] = grouping
        summary["per_repo"] = per_repo_recall_at_10(all_results)
        if subset_name:
            summary["subset_name"] = subset_name
        if compare_baseline:
            summary["compare_baseline"] = compare_baseline
        if git_commit:
            summary["git_commit"] = git_commit
        self.summary_path.write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        return summary

    def _remove_errored_lines(self, errored_ids: set[str]) -> None:
        """Rewrite JSONL, dropping lines for instances in errored_ids."""
        lines = self.per_instance_path.read_text(encoding="utf-8").splitlines()
        kept: list[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                if json.loads(line)["instance_id"] not in errored_ids:
                    kept.append(line)
            except (json.JSONDecodeError, KeyError):
                kept.append(line)
        self.per_instance_path.write_text(
            "\n".join(kept) + ("\n" if kept else ""),
            encoding="utf-8",
        )
