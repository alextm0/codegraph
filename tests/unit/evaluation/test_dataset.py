"""Unit tests for evaluation.dataset."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from evaluation.dataset import (
    SWE_BENCH_LITE,
    DatasetManager,
    group_instances,
)
from tests.unit.evaluation.conftest import make_instance


# ── group_instances ───────────────────────────────────────────────────────────


def test_group_instances_three_groups() -> None:
    instances = [
        (0, make_instance("owner/repoA", "abc", "A1")),
        (1, make_instance("owner/repoB", "def", "B1")),
        (2, make_instance("owner/repoA", "abc", "A2")),
        (3, make_instance("owner/repoC", "ghi", "C1")),
        (4, make_instance("owner/repoB", "def", "B2")),
        (5, make_instance("owner/repoA", "abc", "A3")),
    ]
    groups = group_instances(instances)

    assert len(groups) == 3
    assert groups[0].key == ("owner/repoA", "abc")
    assert groups[1].key == ("owner/repoB", "def")
    assert groups[2].key == ("owner/repoC", "ghi")

    ids_a = [inst["instance_id"] for _, inst in groups[0].instances]
    assert sorted(ids_a) == ["A1", "A2", "A3"]


def test_group_instances_all_unique() -> None:
    instances = [
        (i, make_instance(f"owner/repo{i}", f"commit{i}", f"id{i}"))
        for i in range(5)
    ]
    groups = group_instances(instances)
    assert len(groups) == 5
    for group in groups:
        assert len(group.instances) == 1


def test_group_instances_all_same_key() -> None:
    instances = [
        (i, make_instance("owner/repoX", "samecommit", f"id{i}"))
        for i in range(4)
    ]
    groups = group_instances(instances)
    assert len(groups) == 1
    assert len(groups[0].instances) == 4


def test_group_instances_sorted_by_min_index() -> None:
    instances = [
        (0, make_instance("owner/repoB", "bbb", "B0")),
        (1, make_instance("owner/repoA", "aaa", "A0")),
        (2, make_instance("owner/repoB", "bbb", "B1")),
    ]
    groups = group_instances(instances)
    assert groups[0].key == ("owner/repoB", "bbb")
    assert groups[1].key == ("owner/repoA", "aaa")


def test_dataset_manager_group_delegates() -> None:
    indexed = [(0, make_instance("r/a", "c1", "x"))]
    assert DatasetManager.group(indexed) == group_instances(indexed)


# ── DatasetManager.load ─────────────────────────────────────────────────────


def test_dataset_manager_default_dataset_id() -> None:
    assert DatasetManager().dataset_id == SWE_BENCH_LITE


def _install_mock_datasets(monkeypatch: pytest.MonkeyPatch, return_value: list) -> MagicMock:
    """Inject a fake ``datasets`` module so load() does not need HF installed."""
    mock_load = MagicMock(return_value=return_value)
    ds_mod = types.ModuleType("datasets")
    ds_mod.load_dataset = mock_load
    monkeypatch.setitem(sys.modules, "datasets", ds_mod)
    return mock_load


def test_dataset_manager_load(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_load = _install_mock_datasets(
        monkeypatch, [{"instance_id": "a"}, {"instance_id": "b"}]
    )
    manager = DatasetManager("custom/dataset")

    result = manager.load(split="dev")

    mock_load.assert_called_once_with("custom/dataset", split="dev")
    assert result == [{"instance_id": "a"}, {"instance_id": "b"}]


def test_dataset_manager_load_limited_zero_returns_all(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock_datasets(monkeypatch, [{"i": j} for j in range(10)])
    result = DatasetManager().load_limited(limit=0)
    assert len(result) == 10


def test_dataset_manager_load_limited_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock_datasets(monkeypatch, [{"i": j} for j in range(10)])
    result = DatasetManager().load_limited(limit=3)
    assert len(result) == 3
    assert result[0]["i"] == 0


def test_dataset_manager_load_filtered_by_instance_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {"instance_id": "a", "repo": "org/a"},
        {"instance_id": "b", "repo": "org/b"},
        {"instance_id": "c", "repo": "org/c"},
    ]
    _install_mock_datasets(monkeypatch, rows)
    result = DatasetManager().load_filtered(instance_ids={"a", "c"})
    assert [r["instance_id"] for r in result] == ["a", "c"]


def test_dataset_manager_load_filtered_by_repo_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {"instance_id": "1", "repo": "sympy/sympy"},
        {"instance_id": "2", "repo": "django/django"},
    ]
    _install_mock_datasets(monkeypatch, rows)
    result = DatasetManager().load_filtered(repo_prefix="sympy")
    assert len(result) == 1
    assert result[0]["instance_id"] == "1"


def test_dataset_manager_load_wraps_missing_datasets(monkeypatch) -> None:
    """Missing HuggingFace datasets package yields a helpful ImportError."""
    broken = types.ModuleType("datasets")
    monkeypatch.delitem(sys.modules, "datasets", raising=False)
    monkeypatch.setitem(sys.modules, "datasets", broken)

    with pytest.raises(ImportError, match="codegraph\\[bench\\]"):
        DatasetManager().load()


def test_dataset_manager_load_patchable_at_module_level() -> None:
    """``@patch('evaluation.dataset.load_dataset')`` works for tests that prefer mock.patch."""
    with patch(
        "evaluation.dataset.load_dataset",
        return_value=[{"instance_id": "x"}],
    ) as mock_load:
        assert DatasetManager("id").load(split="train") == [{"instance_id": "x"}]
        mock_load.assert_called_once_with("id", split="train")
