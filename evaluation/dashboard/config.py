"""Normalization and validation helpers for dashboard run configs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evaluation.dashboard.models import RunConfig

_DEFAULT_RETRIEVER = "ppr"
_DEFAULT_ABLATION = "baseline"
_DEFAULT_GROUPING = "repo_commit"
_DEFAULT_CONFIG_PATH = "config.yaml"
_DEFAULT_CACHE_DIR = ".codegraph_cache/repos"
_VALID_RETRIEVERS = {"ppr", "random", "bm25", "one_hop"}
_VALID_GROUPINGS = {"repo_commit", "none"}


@dataclass
class ConfigCheck:
    """Result of validating and normalizing a run configuration."""

    config: RunConfig | None
    warnings: list[str]
    errors: list[str]


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if value is False:
        # Textual Select.BLANK currently resolves to False.
        return ""
    return str(value).strip()


def _valid_ablations() -> set[str]:
    try:
        from evaluation.ablations import ABLATIONS

        names = {a.name for a in ABLATIONS}
        return names or {_DEFAULT_ABLATION}
    except Exception:
        return {_DEFAULT_ABLATION}


def _normalize_grouping(raw_value: Any) -> str:
    if isinstance(raw_value, dict):
        strategy = _safe_str(raw_value.get("strategy"))
        if strategy in _VALID_GROUPINGS:
            return strategy
    value = _safe_str(raw_value)
    if value in _VALID_GROUPINGS:
        return value
    return _DEFAULT_GROUPING


def normalize_and_validate_config(
    config: RunConfig | None,
    *,
    output_dir_fallback: str | None = None,
) -> ConfigCheck:
    """Normalize run config values and return validation result."""
    if config is None:
        return ConfigCheck(
            config=None,
            warnings=[],
            errors=["Run has no stored launch configuration."],
        )

    warnings: list[str] = []
    errors: list[str] = []

    output_dir = _safe_str(config.output_dir) or _safe_str(output_dir_fallback)
    if not output_dir:
        errors.append("Run output directory is missing.")

    retriever = _safe_str(config.retriever)
    if retriever not in _VALID_RETRIEVERS:
        warnings.append(
            f"Invalid retriever value {retriever!r}; using '{_DEFAULT_RETRIEVER}'."
        )
        retriever = _DEFAULT_RETRIEVER

    ablation = _safe_str(config.ablation)
    valid_ablations = _valid_ablations()
    if ablation not in valid_ablations:
        warnings.append(
            f"Invalid ablation value {ablation!r}; using '{_DEFAULT_ABLATION}'."
        )
        ablation = _DEFAULT_ABLATION

    grouping = _normalize_grouping(config.grouping)
    if grouping != _safe_str(config.grouping):
        warnings.append(
            f"Invalid grouping value {config.grouping!r}; using '{grouping}'."
        )

    config_path = _safe_str(config.config_path) or _DEFAULT_CONFIG_PATH
    if config_path != _safe_str(config.config_path):
        warnings.append(
            f"Missing config path; using default '{_DEFAULT_CONFIG_PATH}'."
        )

    cache_dir = _safe_str(config.cache_dir) or _DEFAULT_CACHE_DIR
    if cache_dir != _safe_str(config.cache_dir):
        warnings.append(
            f"Missing cache dir; using default '{_DEFAULT_CACHE_DIR}'."
        )

    limit_value: int
    try:
        limit_value = int(config.limit)
    except (TypeError, ValueError):
        warnings.append(f"Invalid limit value {config.limit!r}; using 0.")
        limit_value = 0
    if limit_value < 0:
        warnings.append(f"Negative limit {limit_value}; using 0.")
        limit_value = 0

    normalized = None
    if not errors:
        normalized = RunConfig(
            output_dir=output_dir,
            retriever=retriever,
            ablation=ablation,
            grouping=grouping,
            limit=limit_value,
            config_path=config_path,
            cache_dir=cache_dir,
            retry_errors=bool(config.retry_errors),
        )

    return ConfigCheck(config=normalized, warnings=warnings, errors=errors)
