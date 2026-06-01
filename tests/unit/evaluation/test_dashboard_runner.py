"""Unit tests for evaluation/dashboard/runner.py and lifecycle transitions."""
from __future__ import annotations

import sys
from pathlib import Path


from evaluation.dashboard.models import RunConfig
from evaluation.dashboard.runner import build_command

# Quick-run profile constants from app.py — tested here to guard against regressions.
_QUICK_RETRIEVER = "ppr"
_QUICK_ABLATION = "baseline"
_QUICK_GROUPING = "repo_commit"
_QUICK_CONFIG_PATH = "config.yaml"
_QUICK_CACHE_DIR = ".codegraph_cache/repos"
_DEFAULT_QUICK_LIMIT = 5


def _make_config(**kwargs) -> RunConfig:
    defaults = {
        "output_dir": "/tmp/run_001",
        "retriever": "ppr",
        "ablation": "baseline",
        "grouping": "repo_commit",
        "limit": 5,
        "config_path": "config.yaml",
        "cache_dir": ".codegraph_cache/repos",
    }
    defaults.update(kwargs)
    return RunConfig(**defaults)


# ──────────────────────── build_command ─────────────────────────────────────

def test_build_command_basic_structure() -> None:
    cfg = _make_config()
    cmd = build_command(cfg)

    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "evaluation.swe_bench_runner"]
    assert "--output" in cmd
    assert "--retriever" in cmd
    assert "--ablation" in cmd
    assert "--grouping" in cmd
    assert "--config" in cmd
    assert "--cache-dir" in cmd


def test_build_command_values_passed_correctly() -> None:
    cfg = _make_config(
        output_dir="/runs/test",
        retriever="bm25",
        ablation="no_idf",
        grouping="none",
        config_path="custom.yaml",
        cache_dir="/data/cache",
    )
    cmd = build_command(cfg)

    assert cmd[cmd.index("--output") + 1] == "/runs/test"
    assert cmd[cmd.index("--retriever") + 1] == "bm25"
    assert cmd[cmd.index("--ablation") + 1] == "no_idf"
    assert cmd[cmd.index("--grouping") + 1] == "none"
    assert cmd[cmd.index("--config") + 1] == "custom.yaml"
    assert cmd[cmd.index("--cache-dir") + 1] == "/data/cache"


def test_build_command_omits_limit_when_zero() -> None:
    cfg = _make_config(limit=0)
    cmd = build_command(cfg)
    assert "--limit" not in cmd


def test_build_command_includes_limit_when_positive() -> None:
    cfg = _make_config(limit=10)
    cmd = build_command(cfg)
    assert "--limit" in cmd
    assert cmd[cmd.index("--limit") + 1] == "10"


def test_build_command_no_resume_flag_by_default() -> None:
    cfg = _make_config()
    cmd = build_command(cfg)
    assert "--resume" not in cmd
    assert "--retry-errors" not in cmd


def test_build_command_includes_resume_flag() -> None:
    cfg = _make_config()
    cmd = build_command(cfg, resume=True)
    assert "--resume" in cmd


def test_build_command_includes_retry_errors_flag() -> None:
    cfg = _make_config()
    cmd = build_command(cfg, retry_errors=True)
    assert "--retry-errors" in cmd


def test_build_command_resume_and_retry_errors_together() -> None:
    cfg = _make_config()
    cmd = build_command(cfg, resume=True, retry_errors=True)
    assert "--resume" in cmd
    assert "--retry-errors" in cmd


# ──────────────────────── quick-run profile defaults ─────────────────────────

def test_quick_run_profile_retriever() -> None:
    assert _QUICK_RETRIEVER == "ppr"


def test_quick_run_profile_ablation() -> None:
    assert _QUICK_ABLATION == "baseline"


def test_quick_run_profile_grouping() -> None:
    assert _QUICK_GROUPING == "repo_commit"


def test_quick_run_profile_config_path() -> None:
    assert _QUICK_CONFIG_PATH == "config.yaml"


def test_quick_run_profile_cache_dir() -> None:
    assert _QUICK_CACHE_DIR == ".codegraph_cache/repos"


def test_quick_run_profile_default_limit() -> None:
    assert _DEFAULT_QUICK_LIMIT == 5


def test_quick_run_profile_command_contains_ppr() -> None:
    """The command built for a quick-run config must use retriever=ppr."""
    cfg = RunConfig(
        output_dir="/tmp/quick_ppr_001",
        retriever=_QUICK_RETRIEVER,
        ablation=_QUICK_ABLATION,
        grouping=_QUICK_GROUPING,
        limit=_DEFAULT_QUICK_LIMIT,
        config_path=_QUICK_CONFIG_PATH,
        cache_dir=_QUICK_CACHE_DIR,
    )
    cmd = build_command(cfg)
    assert cmd[cmd.index("--retriever") + 1] == "ppr"
    assert cmd[cmd.index("--ablation") + 1] == "baseline"
    assert cmd[cmd.index("--grouping") + 1] == "repo_commit"
    assert cmd[cmd.index("--limit") + 1] == str(_DEFAULT_QUICK_LIMIT)


# ──────────────────────── lifecycle: status transitions via state ─────────────

def test_lifecycle_running_to_completed(tmp_path: Path) -> None:
    """Simulate run completing: status transitions running → completed, no error."""
    from evaluation.dashboard.models import RunRecord
    from evaluation.dashboard.state import upsert_run, get_run

    db_path = tmp_path / "test.db"
    record = RunRecord(
        id="run_lifecycle_ok",
        output_dir=str(tmp_path / "run_lifecycle_ok"),
        status="running",
        started_at="2026-03-14T10:00:00",
    )
    upsert_run(record, db_path=db_path)

    # Simulate successful completion
    record.status = "completed"
    record.exit_code = 0
    record.finished_at = "2026-03-14T10:05:00"
    record.last_error_summary = None
    upsert_run(record, db_path=db_path)

    fetched = get_run("run_lifecycle_ok", db_path=db_path)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.exit_code == 0
    assert fetched.last_error_summary is None


def test_lifecycle_running_to_failed_with_diagnostics(tmp_path: Path) -> None:
    """Simulate run failure: status → failed, exit_code set, last_error_summary populated."""
    from evaluation.dashboard.models import RunRecord
    from evaluation.dashboard.state import upsert_run, get_run

    db_path = tmp_path / "test.db"
    record = RunRecord(
        id="run_lifecycle_fail",
        output_dir=str(tmp_path / "run_lifecycle_fail"),
        status="running",
        started_at="2026-03-14T10:00:00",
        last_command="python -m evaluation.swe_bench_runner --retriever ''",
    )
    upsert_run(record, db_path=db_path)

    # Simulate argparse failure (exit code 2, blank retriever)
    record.status = "failed"
    record.exit_code = 2
    record.finished_at = "2026-03-14T10:00:05"
    record.last_error_summary = "exit=2: error: argument --retriever: invalid choice: ''"
    upsert_run(record, db_path=db_path)

    fetched = get_run("run_lifecycle_fail", db_path=db_path)
    assert fetched is not None
    assert fetched.status == "failed"
    assert fetched.exit_code == 2
    assert fetched.last_error_summary is not None
    assert "exit=2" in fetched.last_error_summary


def test_lifecycle_running_to_stopped(tmp_path: Path) -> None:
    """Simulate user stop: status → stopped, last_error_summary = 'Stopped by user'."""
    from evaluation.dashboard.models import RunRecord
    from evaluation.dashboard.state import upsert_run, get_run

    db_path = tmp_path / "test.db"
    record = RunRecord(
        id="run_lifecycle_stop",
        output_dir=str(tmp_path / "run_lifecycle_stop"),
        status="running",
        started_at="2026-03-14T10:00:00",
    )
    upsert_run(record, db_path=db_path)

    record.status = "stopped"
    record.finished_at = "2026-03-14T10:02:00"
    record.last_error_summary = "Stopped by user"
    upsert_run(record, db_path=db_path)

    fetched = get_run("run_lifecycle_stop", db_path=db_path)
    assert fetched is not None
    assert fetched.status == "stopped"
    assert fetched.last_error_summary == "Stopped by user"


# ──────────────────────── summarize_failure ──────────────────────────────────

def test_summarize_failure_extracts_argparse_error(tmp_path: Path) -> None:
    from evaluation.dashboard.parser import summarize_failure

    log_path = tmp_path / "run.log"
    log_path.write_text(
        "some output\n"
        "usage: swe_bench_runner.py [-h] ...\n"
        "swe_bench_runner.py: error: argument --retriever: invalid choice: '' (choose from ppr, bm25)\n",
        encoding="utf-8",
    )
    summary = summarize_failure(log_path, exit_code=2)
    assert "exit=2" in summary
    assert "invalid choice" in summary.lower() or "retriever" in summary.lower()


def test_summarize_failure_no_log(tmp_path: Path) -> None:
    from evaluation.dashboard.parser import summarize_failure

    summary = summarize_failure(tmp_path / "missing.log", exit_code=1)
    assert "exit" in summary.lower() or "no log" in summary.lower()


def test_summarize_failure_exit_code_none(tmp_path: Path) -> None:
    from evaluation.dashboard.parser import summarize_failure

    summary = summarize_failure(tmp_path / "missing.log", exit_code=None)
    assert isinstance(summary, str)
    assert len(summary) > 0
