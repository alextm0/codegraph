"""Human-visible progress for long SWE-bench benchmark runs."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from evaluation.metrics import aggregate_metrics


class BenchmarkProgress:
    """Write stderr status lines and a live ``progress.json`` snapshot."""

    def __init__(
        self,
        output_dir: Path,
        total_instances: int,
        *,
        enabled: bool = True,
    ) -> None:
        self.output_dir = output_dir
        self.total_instances = total_instances
        self.enabled = enabled
        self.completed = 0
        self.errors = 0
        self._started = time.monotonic()
        self.progress_path = output_dir / "progress.json"

    def emit(self, message: str) -> None:
        """Print a single progress line to stderr (always flushed)."""
        if not self.enabled:
            return
        elapsed = time.monotonic() - self._started
        print(f"[bench {elapsed:6.0f}s] {message}", file=sys.stderr, flush=True)

    def phase(self, message: str) -> None:
        """Log a setup/query phase (clone, parse, build, etc.)."""
        self.emit(message)

    def instance_done(self, result: dict, *, group_label: str = "") -> None:
        """Record one finished instance and refresh progress.json."""
        if result.get("error"):
            self.errors += 1
        else:
            self.completed += 1

        r10 = result.get("recall_at_10", 0.0)
        hit = "HIT" if r10 > 0 else "MISS"
        iid = result.get("instance_id", "?")
        seeds = result.get("n_seeds", 0)
        elapsed = result.get("elapsed_seconds", 0)
        prefix = f"{group_label} " if group_label else ""
        self.emit(
            f"{prefix}[{self.completed + self.errors}/{self.total_instances}] "
            f"{iid} {hit} R@10={r10:.0f} seeds={seeds} ({elapsed:.1f}s)"
        )
        self._write_snapshot(last_instance=iid)

    def _write_snapshot(self, last_instance: str | None = None) -> None:
        """Persist running counters and partial metrics to progress.json."""
        snapshot: dict = {
            "total_instances": self.total_instances,
            "finished": self.completed + self.errors,
            "ok": self.completed,
            "errors": self.errors,
            "elapsed_seconds": round(time.monotonic() - self._started, 1),
        }
        if last_instance:
            snapshot["last_instance"] = last_instance

        jsonl = self.output_dir / "per_instance.jsonl"
        if jsonl.exists():
            results = []
            with open(jsonl, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            if results:
                partial = aggregate_metrics(results)
                snapshot["running_mean_recall_at_10"] = partial["mean_recall_at_10"]
                snapshot["running_mean_mrr"] = partial["mean_mrr"]
                snapshot["running_zero_recall"] = partial["instances_with_zero_recall"]

        self.progress_path.write_text(
            json.dumps(snapshot, indent=2),
            encoding="utf-8",
        )

    def finish(self, summary: dict) -> None:
        """Write final banner and merge summary into progress.json."""
        self.emit(
            f"DONE Recall@10={summary.get('mean_recall_at_10', 0):.3f} "
            f"MRR={summary.get('mean_mrr', 0):.3f} "
            f"zero_recall={summary.get('instances_with_zero_recall', 0)}"
        )
        payload = {
            "status": "complete",
            "elapsed_seconds": round(time.monotonic() - self._started, 1),
            **summary,
        }
        self.progress_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
