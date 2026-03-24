"""Unit tests for evaluation/dashboard/config.py."""
from __future__ import annotations

import pytest

from evaluation.dashboard.config import normalize_and_validate_config
from evaluation.dashboard.models import RunConfig


def _base_config(**kwargs) -> RunConfig:
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


# ──────────────────────── None / missing output_dir ─────────────────────────

def test_none_config_returns_error() -> None:
    result = normalize_and_validate_config(None)
    assert result.config is None
    assert result.errors
    assert "no stored launch configuration" in result.errors[0].lower()


def test_missing_output_dir_returns_error() -> None:
    cfg = _base_config(output_dir="")
    result = normalize_and_validate_config(cfg)
    assert result.config is None
    assert any("output directory" in e.lower() for e in result.errors)


def test_output_dir_fallback_used_when_blank() -> None:
    cfg = _base_config(output_dir="")
    result = normalize_and_validate_config(cfg, output_dir_fallback="/fallback/dir")
    assert result.config is not None
    assert result.config.output_dir == "/fallback/dir"
    assert not result.errors


# ──────────────────────── retriever normalization ────────────────────────────

def test_blank_retriever_defaults_to_ppr() -> None:
    cfg = _base_config(retriever="")
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.retriever == "ppr"
    assert result.warnings


def test_invalid_retriever_defaults_to_ppr() -> None:
    cfg = _base_config(retriever="unknown_retriever")
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.retriever == "ppr"
    assert any("retriever" in w.lower() for w in result.warnings)


def test_select_blank_retriever_treated_as_empty() -> None:
    """Select.BLANK resolves to False in Textual; ensure it is treated as empty."""
    cfg = _base_config(retriever=False)  # type: ignore[arg-type]
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.retriever == "ppr"


@pytest.mark.parametrize("retriever", ["ppr", "bm25", "random", "one_hop"])
def test_valid_retrievers_pass_through(retriever: str) -> None:
    cfg = _base_config(retriever=retriever)
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.retriever == retriever
    assert not result.errors


# ──────────────────────── grouping normalization ─────────────────────────────

def test_blank_grouping_defaults_to_repo_commit() -> None:
    cfg = _base_config(grouping="")
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.grouping == "repo_commit"
    assert result.warnings


def test_invalid_grouping_defaults_to_repo_commit() -> None:
    cfg = _base_config(grouping="per_file")
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.grouping == "repo_commit"
    assert any("grouping" in w.lower() for w in result.warnings)


def test_dict_shaped_grouping_normalized() -> None:
    """Legacy dict-shaped grouping (from discovered summary.json) is flattened."""
    cfg = _base_config(grouping={"strategy": "repo_commit", "extra": "data"})  # type: ignore[arg-type]
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.grouping == "repo_commit"


def test_dict_shaped_grouping_invalid_strategy_defaults() -> None:
    cfg = _base_config(grouping={"strategy": "bad_value"})  # type: ignore[arg-type]
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.grouping == "repo_commit"


@pytest.mark.parametrize("grouping", ["repo_commit", "none"])
def test_valid_groupings_pass_through(grouping: str) -> None:
    cfg = _base_config(grouping=grouping)
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.grouping == grouping
    assert not result.errors


# ──────────────────────── limit coercion ────────────────────────────────────

def test_negative_limit_coerced_to_zero() -> None:
    cfg = _base_config(limit=-3)
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.limit == 0
    assert result.warnings


def test_non_integer_limit_coerced_to_zero() -> None:
    cfg = _base_config(limit="bad")  # type: ignore[arg-type]
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.limit == 0
    assert result.warnings


def test_valid_limit_passes_through() -> None:
    cfg = _base_config(limit=10)
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.limit == 10


# ──────────────────────── config_path / cache_dir defaults ──────────────────

def test_blank_config_path_gets_default() -> None:
    cfg = _base_config(config_path="")
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.config_path == "config.yaml"
    assert result.warnings


def test_blank_cache_dir_gets_default() -> None:
    cfg = _base_config(cache_dir="")
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert result.config.cache_dir == ".codegraph_cache/repos"
    assert result.warnings


# ──────────────────────── clean config round-trip ────────────────────────────

def test_valid_config_has_no_warnings_or_errors() -> None:
    cfg = _base_config()
    result = normalize_and_validate_config(cfg)
    assert result.config is not None
    assert not result.errors
    assert not result.warnings
    assert result.config.retriever == "ppr"
    assert result.config.ablation == "baseline"
    assert result.config.grouping == "repo_commit"
    assert result.config.limit == 5
