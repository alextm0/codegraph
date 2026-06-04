"""Unit tests for evaluation.instance_filter."""

import json
from pathlib import Path

import pytest

from evaluation.instance_filter import load_weak_spot_tier, resolve_instance_ids_arg


def test_resolve_weak_spot_tier(tmp_path: Path) -> None:
    data = {
        "tier_a": {"instance_ids": ["x__repo-1", "x__repo-2"]},
    }
    path = tmp_path / "sets.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    ids, label = resolve_instance_ids_arg(f"{path}:tier_a")
    assert label == "tier_a"
    assert ids == {"x__repo-1", "x__repo-2"}


def test_resolve_plain_list(tmp_path: Path) -> None:
    path = tmp_path / "ids.json"
    path.write_text(json.dumps(["a", "b"]), encoding="utf-8")
    ids, label = resolve_instance_ids_arg(str(path))
    assert ids == {"a", "b"}
    assert label == "ids"


def test_load_weak_spot_tier_unknown_key(tmp_path: Path) -> None:
    path = tmp_path / "sets.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(KeyError):
        load_weak_spot_tier(path, "missing")
