"""Incremental JSONL reader and progress metrics for dashboard."""
from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path

from evaluation.dashboard.models import InstanceRecord, LiveProgress

logger = logging.getLogger(__name__)


def read_instances(jsonl_path: Path, offset: int = 0) -> tuple[list[InstanceRecord], int]:
    """
    Read new instances from a JSONL file starting at the given offset.

    Args:
        jsonl_path: Path to the per_instance.jsonl file.
        offset: Byte offset to start reading from.

    Returns:
        Tuple of (list of InstanceRecord objects, new byte offset after reading).
        If file doesn't exist, returns ([], 0).
    """
    if not jsonl_path.exists():
        return [], 0

    instances = []
    with open(jsonl_path, "rb") as f:
        f.seek(offset)
        data = f.read()
        new_offset = f.tell()

    # Split on newlines and parse each non-empty line
    lines = data.decode("utf-8", errors="replace").split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
            # Note: JSONL includes 'total_nodes' but InstanceRecord doesn't have that field
            # Construct InstanceRecord from the relevant fields
            instance = InstanceRecord(
                instance_id=obj["instance_id"],
                repo=obj["repo"],
                gold_files=obj["gold_files"],
                predicted_files=obj["predicted_files"],
                recall_at_5=obj["recall_at_5"],
                recall_at_10=obj["recall_at_10"],
                mrr=obj["mrr"],
                n_seeds=obj["n_seeds"],
                elapsed_seconds=obj["elapsed_seconds"],
                error=obj.get("error"),
            )
            instances.append(instance)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Skipping malformed JSON line in {jsonl_path}: {e}")

    return instances, new_offset


def compute_live_progress(
    instances: list[InstanceRecord], started_at: datetime, n_total: int | None
) -> LiveProgress:
    """
    Compute live progress metrics from parsed instances.

    Args:
        instances: List of parsed InstanceRecord objects.
        started_at: Datetime when the run started.
        n_total: Total number of instances expected, or None if unknown.

    Returns:
        LiveProgress object with computed metrics.
    """
    n_done = len(instances)
    n_errors = sum(1 for instance in instances if instance.error is not None)

    # Success instances are those with no error
    success_instances = [instance for instance in instances if instance.error is None]

    # Compute mean metrics (0.0 if no successful instances)
    if success_instances:
        mean_recall_at_10 = sum(instance.recall_at_10 for instance in success_instances) / len(
            success_instances
        )
        mean_mrr = sum(instance.mrr for instance in success_instances) / len(success_instances)
    else:
        mean_recall_at_10 = 0.0
        mean_mrr = 0.0

    # Compute throughput
    elapsed = (datetime.now() - started_at).total_seconds()
    elapsed_hours = elapsed / 3600
    throughput_per_hour = n_done / elapsed_hours if elapsed_hours > 0 else 0.0

    # Compute ETA
    eta_seconds = None
    if throughput_per_hour > 0 and n_total is not None and n_total > n_done:
        remaining_instances = n_total - n_done
        eta_seconds = (remaining_instances / throughput_per_hour) * 3600

    return LiveProgress(
        n_done=n_done,
        n_errors=n_errors,
        n_total=n_total,
        mean_recall_at_10=mean_recall_at_10,
        mean_mrr=mean_mrr,
        throughput_per_hour=throughput_per_hour,
        eta_seconds=eta_seconds,
    )


def read_log_tail(log_path: Path, n_lines: int = 100) -> list[str]:
    """
    Read the last n lines from a log file efficiently.

    Args:
        log_path: Path to the log file.
        n_lines: Number of lines to read from the end.

    Returns:
        List of strings (with newlines stripped).
        Returns empty list if file doesn't exist.
    """
    if not log_path.exists():
        return []

    lines = deque(maxlen=n_lines)
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                lines.append(line.rstrip("\n\r"))
    except Exception as e:
        logger.warning(f"Error reading log tail from {log_path}: {e}")
        return []

    return list(lines)


def summarize_failure(log_path: Path, exit_code: int | None, *, n_lines: int = 200) -> str:
    """Build a short actionable error summary from the end of run.log."""
    lines = read_log_tail(log_path, n_lines=n_lines)
    if not lines:
        if exit_code is None:
            return "Run failed with no log output."
        return f"Process exited with code {exit_code} (no log output)."

    interesting: list[str] = []
    for line in reversed(lines):
        text = line.strip()
        if not text:
            continue
        lowered = text.lower()
        if (
            "error:" in lowered
            or lowered.startswith("traceback")
            or "exception" in lowered
            or "failed" in lowered
            or "invalid choice" in lowered
        ):
            interesting.append(text)
        if len(interesting) >= 3:
            break

    if interesting:
        summary = " | ".join(reversed(interesting))
    else:
        summary = lines[-1].strip() or "Run failed (see log)."

    prefix = f"exit={exit_code}: " if exit_code is not None else ""
    return f"{prefix}{summary}"[:500]
