"""Unit tests for evaluation.progress."""

import json
from pathlib import Path

from evaluation.progress import BenchmarkProgress


def test_progress_writes_snapshot(tmp_path: Path) -> None:
    out = tmp_path / "run"
    out.mkdir()
    (out / "per_instance.jsonl").write_text(
        json.dumps({"recall_at_10": 1.0, "recall_at_5": 1.0, "mrr": 1.0}) + "\n",
        encoding="utf-8",
    )
    prog = BenchmarkProgress(out, total_instances=2, enabled=False)
    prog.completed = 1
    prog._write_snapshot(last_instance="a")

    data = json.loads((out / "progress.json").read_text(encoding="utf-8"))
    assert data["finished"] == 1
    assert data["running_mean_recall_at_10"] == 1.0
