"""Data models for the evaluation dashboard."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunConfig:
    """Configuration for an evaluation run."""

    output_dir: str
    retriever: str  # ppr | bm25 | random | one_hop
    ablation: str  # name from ABLATIONS list e.g. "baseline"
    grouping: str  # repo_commit | none
    limit: int  # 0 = all instances
    config_path: str  # path to config.yaml
    cache_dir: str  # default .codegraph_cache/repos
    retry_errors: bool = False


@dataclass
class RunRecord:
    """Record of a single evaluation run."""

    id: str  # e.g. run_20260314_143022
    output_dir: str
    status: str  # queued | running | completed | failed | stopped
    started_at: str | None = None
    finished_at: str | None = None
    config: RunConfig | None = None
    pid: int | None = None
    exit_code: int | None = None
    last_error_summary: str | None = None
    last_command: str | None = None


@dataclass
class InstanceRecord:
    """Results for a single evaluation instance."""

    instance_id: str
    repo: str
    gold_files: list[str]
    predicted_files: list[str]
    recall_at_5: float
    recall_at_10: float
    mrr: float
    n_seeds: int
    elapsed_seconds: float
    error: str | None = None


@dataclass
class LiveProgress:
    """Live progress metrics for an ongoing run."""

    n_done: int
    n_errors: int
    n_total: int | None  # None until we know total instance count
    mean_recall_at_10: float
    mean_mrr: float
    throughput_per_hour: float
    eta_seconds: float | None
