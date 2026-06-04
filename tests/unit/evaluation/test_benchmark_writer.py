"""Unit tests for evaluation.benchmark_writer."""

import io
import json
from pathlib import Path

from evaluation.benchmark_writer import ReportWriter, flush_ordered
from tests.unit.evaluation.conftest import make_result


# ── flush_ordered ───────────────────────────────────────────────────────────


def test_flush_ordered_contiguous() -> None:
    buf = {0: make_result(0), 1: make_result(1), 2: make_result(2)}
    out = io.StringIO()
    next_idx = flush_ordered(buf, 0, out)

    assert next_idx == 3
    assert buf == {}
    lines = [line for line in out.getvalue().splitlines() if line]
    assert [json.loads(line)["idx"] for line in lines] == [0, 1, 2]


def test_flush_ordered_gap_stops_at_boundary() -> None:
    buf = {0: make_result(0), 1: make_result(1), 3: make_result(3)}
    out = io.StringIO()
    next_idx = flush_ordered(buf, 0, out)

    assert next_idx == 2
    assert set(buf.keys()) == {3}
    lines = [line for line in out.getvalue().splitlines() if line]
    assert len(lines) == 2


def test_flush_ordered_force_all() -> None:
    buf = {0: make_result(0), 2: make_result(2), 4: make_result(4)}
    out = io.StringIO()
    flush_ordered(buf, 0, out, force_all=True)

    assert buf == {}
    lines = [line for line in out.getvalue().splitlines() if line]
    assert [json.loads(line)["idx"] for line in lines] == [0, 2, 4]


def test_flush_ordered_empty_buffer() -> None:
    buf: dict[int, dict] = {}
    out = io.StringIO()
    next_idx = flush_ordered(buf, 5, out)
    assert next_idx == 5
    assert out.getvalue() == ""


# ── ReportWriter ──────────────────────────────────────────────────────────────


def _result_line(instance_id: str, error: str | None = None) -> str:
    rec = {
        "instance_id": instance_id,
        "recall_at_5": 1.0 if not error else 0.0,
        "recall_at_10": 1.0 if not error else 0.0,
        "mrr": 1.0 if not error else 0.0,
    }
    if error:
        rec["error"] = error
    return json.dumps(rec)


def test_report_writer_creates_output_dir(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "run_001"
    writer = ReportWriter(out)
    assert writer.output_dir.exists()
    assert writer.per_instance_path == out / "per_instance.jsonl"
    assert writer.summary_path == out / "summary.json"


def test_report_writer_load_resume_state_no_file(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path)
    completed, errored = writer.load_resume_state(resume=True, retry_errors=False)
    assert completed == set()
    assert errored == set()


def test_report_writer_load_resume_state_completed_and_errored(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path)
    writer.per_instance_path.write_text(
        _result_line("ok-1") + "\n" + _result_line("err-1", "failed") + "\n",
        encoding="utf-8",
    )

    completed, errored = writer.load_resume_state(resume=True, retry_errors=False)

    assert completed == {"ok-1", "err-1"}
    assert errored == {"err-1"}


def test_report_writer_retry_errors_removes_errored_lines(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path)
    writer.per_instance_path.write_text(
        _result_line("ok-1") + "\n" + _result_line("err-1", "boom") + "\n",
        encoding="utf-8",
    )

    completed, errored = writer.load_resume_state(resume=True, retry_errors=True)

    assert errored == {"err-1"}
    assert completed == {"ok-1"}
    content = writer.per_instance_path.read_text(encoding="utf-8")
    assert "err-1" not in content
    assert "ok-1" in content


def test_report_writer_open_jsonl_append_mode(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path)
    writer.per_instance_path.write_text('{"instance_id":"x"}\n', encoding="utf-8")

    with writer.open_jsonl(append=True) as fh:
        fh.write('{"instance_id":"y"}\n')

    lines = writer.per_instance_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_report_writer_read_all_results_skips_bad_lines(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path)
    writer.per_instance_path.write_text(
        '{"instance_id":"a"}\nnot json\n{"instance_id":"b"}\n',
        encoding="utf-8",
    )

    results = writer.read_all_results()
    assert [r["instance_id"] for r in results] == ["a", "b"]


def test_report_writer_write_summary(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path)
    results = [
        {
            "instance_id": "a",
            "recall_at_5": 1.0,
            "recall_at_10": 1.0,
            "mrr": 1.0,
        },
        {
            "instance_id": "b",
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "mrr": 0.0,
        },
    ]

    summary = writer.write_summary(
        results, "baseline", "ppr", {"strategy": "repo_commit"}
    )

    assert summary["ablation"] == "baseline"
    assert summary["retriever"] == "ppr"
    assert summary["grouping"]["strategy"] == "repo_commit"
    assert summary["n_instances"] == 2
    assert writer.summary_path.exists()
    on_disk = json.loads(writer.summary_path.read_text(encoding="utf-8"))
    assert on_disk["mean_recall_at_10"] == summary["mean_recall_at_10"]
