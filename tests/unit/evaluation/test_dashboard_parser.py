"""Unit tests for evaluation/dashboard/parser.py."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


from evaluation.dashboard.models import InstanceRecord
from evaluation.dashboard.parser import compute_live_progress, read_instances, read_log_tail
from evaluation.dashboard.state import discover_existing_runs


def _make_instance(instance_id: str = "repo__proj-1", error: str | None = None) -> dict:
    return {
        "instance_id": instance_id,
        "repo": "repo/proj",
        "gold_files": ["src/foo.py"],
        "predicted_files": ["src/foo.py", "src/bar.py"],
        "recall_at_5": 1.0,
        "recall_at_10": 1.0,
        "mrr": 1.0,
        "n_seeds": 3,
        "total_nodes": 500,
        "elapsed_seconds": 10.0,
        "error": error,
    }


# ──────────────────────── read_instances ────────────────────────────────────

def test_incremental_read(tmp_path: Path) -> None:
    """Read from byte offset returns only new records."""
    jsonl = tmp_path / "per_instance.jsonl"

    # Write 3 lines
    line_a = json.dumps(_make_instance("inst-a")) + "\n"
    line_b = json.dumps(_make_instance("inst-b")) + "\n"
    line_c = json.dumps(_make_instance("inst-c")) + "\n"
    jsonl.write_text(line_a + line_b + line_c, encoding="utf-8")

    # First read from offset 0 → 3 records
    records, offset = read_instances(jsonl, offset=0)
    assert len(records) == 3
    assert {r.instance_id for r in records} == {"inst-a", "inst-b", "inst-c"}
    assert offset > 0

    # Append 2 more lines
    with open(jsonl, "a", encoding="utf-8") as f:
        f.write(json.dumps(_make_instance("inst-d")) + "\n")
        f.write(json.dumps(_make_instance("inst-e")) + "\n")

    # Second read from saved offset → only 2 new records
    new_records, new_offset = read_instances(jsonl, offset=offset)
    assert len(new_records) == 2
    assert {r.instance_id for r in new_records} == {"inst-d", "inst-e"}
    assert new_offset > offset


def test_read_instances_missing_file(tmp_path: Path) -> None:
    """Missing file returns empty list and offset 0."""
    records, offset = read_instances(tmp_path / "nonexistent.jsonl")
    assert records == []
    assert offset == 0


def test_read_instances_skips_malformed_lines(tmp_path: Path) -> None:
    """Malformed JSON lines are skipped without crashing."""
    jsonl = tmp_path / "per_instance.jsonl"
    jsonl.write_text(
        json.dumps(_make_instance("good-1")) + "\n"
        + "NOT VALID JSON\n"
        + json.dumps(_make_instance("good-2")) + "\n",
        encoding="utf-8",
    )
    records, _ = read_instances(jsonl)
    assert len(records) == 2
    assert {r.instance_id for r in records} == {"good-1", "good-2"}


# ──────────────────────── compute_live_progress ─────────────────────────────

def _make_record(instance_id: str, recall: float = 1.0, mrr: float = 1.0, error: str | None = None) -> InstanceRecord:
    return InstanceRecord(
        instance_id=instance_id,
        repo="repo/proj",
        gold_files=["src/foo.py"],
        predicted_files=["src/foo.py"],
        recall_at_5=recall,
        recall_at_10=recall,
        mrr=mrr,
        n_seeds=3,
        elapsed_seconds=10.0,
        error=error,
    )


def test_errors_excluded_from_metrics() -> None:
    """Error instances are counted in n_errors but excluded from recall/MRR means."""
    started = datetime.now() - timedelta(minutes=5)
    instances = [
        _make_record("ok-1", recall=1.0, mrr=1.0),
        _make_record("ok-2", recall=0.5, mrr=0.5),
        _make_record("err-1", recall=0.0, mrr=0.0, error="Neo4j connection failed"),
    ]
    prog = compute_live_progress(instances, started, n_total=10)

    assert prog.n_done == 3
    assert prog.n_errors == 1
    # mean over success instances only: (1.0 + 0.5) / 2 = 0.75
    assert abs(prog.mean_recall_at_10 - 0.75) < 1e-9
    assert abs(prog.mean_mrr - 0.75) < 1e-9


def test_all_errors_gives_zero_metrics() -> None:
    """When all instances errored, metrics default to 0.0."""
    started = datetime.now() - timedelta(minutes=1)
    instances = [
        _make_record("err-1", error="fail"),
        _make_record("err-2", error="fail"),
    ]
    prog = compute_live_progress(instances, started, n_total=5)
    assert prog.n_errors == 2
    assert prog.mean_recall_at_10 == 0.0
    assert prog.mean_mrr == 0.0


def test_eta_calculation() -> None:
    """ETA is correct given known throughput and remaining count."""
    # 10 done in 1 hour → throughput = 10/hr; 5 remaining → ETA = 0.5 hr = 1800 s
    started = datetime.now() - timedelta(hours=1)
    instances = [_make_record(f"inst-{i}") for i in range(10)]
    prog = compute_live_progress(instances, started, n_total=15)

    assert prog.n_done == 10
    assert prog.throughput_per_hour > 0
    assert prog.eta_seconds is not None
    # Allow 5% tolerance for timing jitter
    assert abs(prog.eta_seconds - 1800) < 90  # within 1.5 min of exact


def test_eta_none_when_no_total() -> None:
    """ETA is None when n_total is not known."""
    started = datetime.now() - timedelta(minutes=10)
    instances = [_make_record("inst-1")]
    prog = compute_live_progress(instances, started, n_total=None)
    assert prog.eta_seconds is None


def test_eta_none_when_already_done() -> None:
    """ETA is None when n_done >= n_total."""
    started = datetime.now() - timedelta(minutes=10)
    instances = [_make_record(f"inst-{i}") for i in range(5)]
    prog = compute_live_progress(instances, started, n_total=5)
    assert prog.eta_seconds is None


# ──────────────────────── read_log_tail ─────────────────────────────────────

def test_read_log_tail(tmp_path: Path) -> None:
    """read_log_tail returns last n lines."""
    log = tmp_path / "run.log"
    lines = [f"line {i}" for i in range(200)]
    log.write_text("\n".join(lines), encoding="utf-8")

    tail = read_log_tail(log, n_lines=50)
    assert len(tail) == 50
    assert tail[-1] == "line 199"
    assert tail[0] == "line 150"


def test_read_log_tail_missing_file(tmp_path: Path) -> None:
    """Missing log file returns empty list."""
    result = read_log_tail(tmp_path / "no_log.log")
    assert result == []


# ──────────────────────── discover_existing_runs ────────────────────────────

def test_discover_existing_runs(tmp_path: Path) -> None:
    """discover_existing_runs finds result subdirs and inserts them as completed/stopped."""
    # Create two result directories
    run_a = tmp_path / "run_a"
    run_a.mkdir()
    (run_a / "summary.json").write_text(
        json.dumps({"n_instances": 5, "ablation": "baseline", "retriever": "ppr"}),
        encoding="utf-8",
    )
    (run_a / "per_instance.jsonl").write_text("", encoding="utf-8")

    run_b = tmp_path / "run_b"
    run_b.mkdir()
    (run_b / "per_instance.jsonl").write_text(
        json.dumps(_make_instance("inst-1")) + "\n", encoding="utf-8"
    )
    # run_b has no summary.json → should be status=stopped

    # Empty dir (no qualifying files) → should be ignored
    (tmp_path / "empty_dir").mkdir()

    db_path = tmp_path / "test_runs.db"
    count = discover_existing_runs(tmp_path, db_path=db_path)

    assert count == 2

    from evaluation.dashboard.state import list_runs, get_run
    runs = list_runs(db_path=db_path)
    assert len(runs) == 2

    ids = {r.id for r in runs}
    assert "run_a" in ids
    assert "run_b" in ids

    run_a_rec = get_run("run_a", db_path=db_path)
    assert run_a_rec is not None
    assert run_a_rec.status == "completed"

    run_b_rec = get_run("run_b", db_path=db_path)
    assert run_b_rec is not None
    assert run_b_rec.status == "stopped"


def test_discover_existing_runs_skips_known(tmp_path: Path) -> None:
    """discover_existing_runs does not duplicate already-known runs."""
    run_dir = tmp_path / "run_x"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps({"n_instances": 1}), encoding="utf-8")

    db_path = tmp_path / "test_runs.db"

    # First discovery
    count1 = discover_existing_runs(tmp_path, db_path=db_path)
    assert count1 == 1

    # Second discovery → already known, count = 0
    count2 = discover_existing_runs(tmp_path, db_path=db_path)
    assert count2 == 0
