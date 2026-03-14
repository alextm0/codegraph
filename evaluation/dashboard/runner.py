"""Process lifecycle management for evaluation runs."""
from __future__ import annotations

import asyncio
import signal
import subprocess
import sys
from pathlib import Path

from evaluation.dashboard.models import RunConfig


async def start_run(config: RunConfig, run_id: str) -> asyncio.subprocess.Process:
    """Spawn swe_bench_runner as a subprocess, redirecting stdout+stderr to run.log."""
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "evaluation.swe_bench_runner",
        "--output", config.output_dir,
        "--retriever", config.retriever,
        "--ablation", config.ablation,
        "--grouping", config.grouping,
        "--config", config.config_path,
        "--cache-dir", config.cache_dir,
    ]
    if config.limit > 0:
        cmd += ["--limit", str(config.limit)]

    log_file = open(output_dir / "run.log", "a")

    kwargs: dict = {
        "stdout": log_file,
        "stderr": asyncio.subprocess.STDOUT,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    return await asyncio.create_subprocess_exec(*cmd, **kwargs)


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
) -> asyncio.subprocess.Process:
    """Resume a stopped/failed run by restarting with --resume."""
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "evaluation.swe_bench_runner",
        "--output", config.output_dir,
        "--retriever", config.retriever,
        "--ablation", config.ablation,
        "--grouping", config.grouping,
        "--config", config.config_path,
        "--cache-dir", config.cache_dir,
        "--resume",
    ]
    if config.limit > 0:
        cmd += ["--limit", str(config.limit)]
    if retry_errors:
        cmd.append("--retry-errors")

    log_file = open(output_dir / "run.log", "a")

    kwargs: dict = {
        "stdout": log_file,
        "stderr": asyncio.subprocess.STDOUT,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    return await asyncio.create_subprocess_exec(*cmd, **kwargs)
