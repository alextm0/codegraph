"""Process lifecycle management for evaluation runs."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import signal
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from evaluation.dashboard.models import RunConfig

# Project root is two levels up from this file (evaluation/dashboard/runner.py)
_PROJECT_ROOT = Path(__file__).parents[2]


@dataclass
class LaunchInfo:
    """Metadata returned when spawning a benchmark process."""

    process: asyncio.subprocess.Process
    command: list[str]
    command_display: str
    log_path: Path
    cwd: str


def build_command(
    config: RunConfig,
    *,
    resume: bool = False,
    retry_errors: bool = False,
) -> list[str]:
    """Build command args used to launch swe_bench_runner."""
    cmd = [
        sys.executable,
        "-m",
        "evaluation.swe_bench_runner",
        "--output",
        config.output_dir,
        "--retriever",
        config.retriever,
        "--ablation",
        config.ablation,
        "--grouping",
        config.grouping,
        "--config",
        config.config_path,
        "--cache-dir",
        config.cache_dir,
    ]
    if config.limit > 0:
        cmd += ["--limit", str(config.limit)]
    if resume:
        cmd.append("--resume")
    if retry_errors:
        cmd.append("--retry-errors")
    return cmd


def _format_command(cmd: list[str]) -> str:
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmd)
    return shlex.join(cmd)


def _write_run_header(
    log_file,
    *,
    run_id: str,
    mode: str,
    config: RunConfig,
    command_display: str,
) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    log_file.write("\n")
    log_file.write("=" * 78 + "\n")
    log_file.write(f"[dashboard] {mode.upper()} run {run_id} at {timestamp}\n")
    log_file.write(f"[dashboard] cwd: {_PROJECT_ROOT}\n")
    log_file.write(f"[dashboard] cmd: {command_display}\n")
    log_file.write(
        "[dashboard] profile: "
        f"retriever={config.retriever}, "
        f"ablation={config.ablation}, "
        f"grouping={config.grouping}, "
        f"limit={config.limit}, "
        f"config={config.config_path}, "
        f"cache={config.cache_dir}\n"
    )
    log_file.write("=" * 78 + "\n")
    log_file.flush()


async def _spawn(
    *,
    run_id: str,
    config: RunConfig,
    cmd: list[str],
    mode: str,
) -> LaunchInfo:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"
    command_display = _format_command(cmd)

    log_file = open(log_path, "a", encoding="utf-8")
    _write_run_header(
        log_file,
        run_id=run_id,
        mode=mode,
        config=config,
        command_display=command_display,
    )

    kwargs: dict = {
        "stdout": log_file,
        "stderr": asyncio.subprocess.STDOUT,
        "cwd": str(_PROJECT_ROOT),
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, **kwargs)
    except Exception:
        log_file.write("[dashboard] Failed to start subprocess.\n")
        log_file.flush()
        log_file.close()
        raise

    # Keep handle alive while process runs, then close on process completion.
    setattr(proc, "_dashboard_log_file", log_file)

    return LaunchInfo(
        process=proc,
        command=cmd,
        command_display=command_display,
        log_path=log_path,
        cwd=str(_PROJECT_ROOT),
    )


async def start_run(config: RunConfig, run_id: str) -> LaunchInfo:
    """Spawn swe_bench_runner as a subprocess, redirecting stdout+stderr to run.log."""
    cmd = build_command(config, resume=False, retry_errors=False)
    return await _spawn(run_id=run_id, config=config, cmd=cmd, mode="start")


async def stop_run(proc: asyncio.subprocess.Process, timeout: float = 10.0) -> None:
    """Gracefully stop a running process (CTRL_BREAK on Windows, SIGTERM elsewhere)."""
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return  # already exited

    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except (ProcessLookupError, OSError):
            pass


async def resume_run(
    config: RunConfig, run_id: str, retry_errors: bool = False
) -> LaunchInfo:
    """Resume a stopped/failed run by restarting with --resume."""
    cmd = build_command(config, resume=True, retry_errors=retry_errors)
    return await _spawn(run_id=run_id, config=config, cmd=cmd, mode="resume")
