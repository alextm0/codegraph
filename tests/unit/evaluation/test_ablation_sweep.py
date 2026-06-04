"""Unit tests for evaluation.run_ablation_sweep."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from evaluation.ablations import resolve_preset
from evaluation.run_ablation_sweep import (
    SweepJob,
    _is_complete,
    _pick_best,
    _should_resume,
    build_jobs,
)


def test_resolve_preset_quick() -> None:
    names = resolve_preset("quick")
    assert "baseline" in names
    assert "ppr_weighted" in names


def test_build_jobs_with_file_rank_variant() -> None:
    jobs = build_jobs(["baseline"], include_file_rank_variants=True)
    assert len(jobs) == 2
    assert jobs[1].output_name == "baseline_max_score"
    assert jobs[1].file_rank_by == "max_score"


def test_is_complete_checks_n_instances(tmp_path: Path) -> None:
    out = tmp_path / "run"
    out.mkdir()
    (out / "summary.json").write_text(
        json.dumps({"n_instances": 50, "mean_recall_at_10": 0.5}),
        encoding="utf-8",
    )
    assert _is_complete(out, 50) is True
    assert _is_complete(out, 51) is False


def test_should_resume_partial_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "run"
    out.mkdir()
    (out / "per_instance.jsonl").write_text('{"instance_id":"x"}\n', encoding="utf-8")
    assert _should_resume(out, 50) is True
    (out / "summary.json").write_text(
        json.dumps({"n_instances": 50}),
        encoding="utf-8",
    )
    assert _should_resume(out, 50) is False


def test_pick_best_prefers_recall_then_zero_recall() -> None:
    rows = [
        ("a", {"mean_recall_at_10": 0.70, "instances_with_zero_recall": 10, "mean_mrr": 0.4}),
        ("b", {"mean_recall_at_10": 0.72, "instances_with_zero_recall": 15, "mean_mrr": 0.5}),
        ("c", {"mean_recall_at_10": 0.72, "instances_with_zero_recall": 8, "mean_mrr": 0.3}),
    ]
    label, _ = _pick_best(rows)
    assert label == "c"


@patch("evaluation.run_ablation_sweep._run_single", return_value=0)
def test_run_sweep_dry_run_skips_subprocess(mock_run: MagicMock) -> None:
    from evaluation.run_ablation_sweep import run_sweep

    code = run_sweep(
        [SweepJob("baseline", "baseline")],
        output_root=Path("/tmp/unused"),
        limit=5,
        expected_instances=5,
        cache_dir="/cache",
        config_path="config.yaml",
        dry_run=True,
    )
    assert code == 0
    mock_run.assert_not_called()
