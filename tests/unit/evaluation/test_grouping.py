"""Unit tests for _group_instances() and _flush_ordered()."""

import io
import json

import pytest

from evaluation.swe_bench_runner import InstanceGroup, _flush_ordered, _group_instances


# ── Helpers ───────────────────────────────────────────────────────────────────

def _inst(repo: str, base_commit: str, instance_id: str | None = None) -> dict:
    return {
        "repo": repo,
        "base_commit": base_commit,
        "instance_id": instance_id or f"{repo}_{base_commit[:8]}",
        "problem_statement": "fix something",
        "patch": "",
    }


# ── _group_instances ──────────────────────────────────────────────────────────

def test_group_instances_three_groups() -> None:
    instances = [
        (0, _inst("owner/repoA", "abc", "A1")),
        (1, _inst("owner/repoB", "def", "B1")),
        (2, _inst("owner/repoA", "abc", "A2")),
        (3, _inst("owner/repoC", "ghi", "C1")),
        (4, _inst("owner/repoB", "def", "B2")),
        (5, _inst("owner/repoA", "abc", "A3")),
    ]
    groups = _group_instances(instances)

    assert len(groups) == 3
    # Sorted by min index: repoA(0), repoB(1), repoC(3)
    assert groups[0].key == ("owner/repoA", "abc")
    assert groups[1].key == ("owner/repoB", "def")
    assert groups[2].key == ("owner/repoC", "ghi")

    ids_a = [inst["instance_id"] for _, inst in groups[0].instances]
    assert sorted(ids_a) == ["A1", "A2", "A3"]

    ids_b = [inst["instance_id"] for _, inst in groups[1].instances]
    assert sorted(ids_b) == ["B1", "B2"]

    ids_c = [inst["instance_id"] for _, inst in groups[2].instances]
    assert ids_c == ["C1"]


def test_group_instances_all_unique() -> None:
    instances = [
        (i, _inst(f"owner/repo{i}", f"commit{i}", f"id{i}"))
        for i in range(5)
    ]
    groups = _group_instances(instances)
    assert len(groups) == 5
    for g in groups:
        assert len(g.instances) == 1


def test_group_instances_all_same_key() -> None:
    instances = [
        (i, _inst("owner/repoX", "samecommit", f"id{i}"))
        for i in range(4)
    ]
    groups = _group_instances(instances)
    assert len(groups) == 1
    assert len(groups[0].instances) == 4


def test_group_instances_sorted_by_min_index() -> None:
    # Insert in reverse order so that group B has a lower min index than group A.
    instances = [
        (0, _inst("owner/repoB", "bbb", "B0")),
        (1, _inst("owner/repoA", "aaa", "A0")),
        (2, _inst("owner/repoB", "bbb", "B1")),
    ]
    groups = _group_instances(instances)
    assert groups[0].key == ("owner/repoB", "bbb")
    assert groups[1].key == ("owner/repoA", "aaa")


# ── _flush_ordered ────────────────────────────────────────────────────────────

def _make_result(idx: int) -> dict:
    return {"instance_id": f"inst_{idx}", "idx": idx}


def test_flush_ordered_contiguous() -> None:
    buf = {0: _make_result(0), 1: _make_result(1), 2: _make_result(2)}
    out = io.StringIO()
    next_idx = _flush_ordered(buf, 0, out)

    assert next_idx == 3
    assert buf == {}
    lines = [l for l in out.getvalue().splitlines() if l]
    assert len(lines) == 3
    assert [json.loads(l)["idx"] for l in lines] == [0, 1, 2]


def test_flush_ordered_gap_stops_at_boundary() -> None:
    # 0 and 1 are present, 2 is missing, 3 is present.
    buf = {0: _make_result(0), 1: _make_result(1), 3: _make_result(3)}
    out = io.StringIO()
    next_idx = _flush_ordered(buf, 0, out)

    assert next_idx == 2
    assert set(buf.keys()) == {3}
    lines = [l for l in out.getvalue().splitlines() if l]
    assert len(lines) == 2
    assert [json.loads(l)["idx"] for l in lines] == [0, 1]


def test_flush_ordered_force_all() -> None:
    # There is a gap (1 missing) but force_all=True should flush everything.
    buf = {0: _make_result(0), 2: _make_result(2), 4: _make_result(4)}
    out = io.StringIO()
    _flush_ordered(buf, 0, out, force_all=True)

    assert buf == {}
    lines = [l for l in out.getvalue().splitlines() if l]
    # force_all sorts by key
    assert [json.loads(l)["idx"] for l in lines] == [0, 2, 4]


def test_flush_ordered_empty_buffer() -> None:
    buf: dict[int, dict] = {}
    out = io.StringIO()
    next_idx = _flush_ordered(buf, 5, out)
    assert next_idx == 5
    assert out.getvalue() == ""


# ── Output order end-to-end (mock setup_group + run_instance_query) ──────────

def test_output_order_preserved_end_to_end(monkeypatch) -> None:
    """Verify that grouped mode writes results in original dataset order."""
    from unittest.mock import MagicMock, patch

    from evaluation.swe_bench_runner import _run_grouped

    all_instances = [
        _inst("owner/repoA", "abc", f"A{i}") for i in range(3)
    ] + [
        _inst("owner/repoB", "def", f"B{i}") for i in range(2)
    ]

    # pending = all instances (no completed)
    pending = all_instances[:]

    call_order: list[str] = []

    def fake_setup(group_key, driver, gds, parser, cache_dir, ablation, retriever):
        return 10, "/fake/path", None, None

    def fake_query(instance, *a, **kw):
        iid = instance["instance_id"]
        call_order.append(iid)
        return {
            "instance_id": iid,
            "repo": instance["repo"],
            "gold_files": [],
            "predicted_files": [],
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "mrr": 0.0,
            "n_seeds": 0,
            "total_nodes": 10,
            "elapsed_seconds": 0.0,
            "error": None,
        }

    args = MagicMock()
    args.cache_dir = "/cache"
    args.retriever = "ppr"
    args.failure_streak_threshold = 5

    ablation = MagicMock()

    out = io.StringIO()

    with patch("evaluation.swe_bench_runner.setup_group", side_effect=fake_setup), \
         patch("evaluation.swe_bench_runner.run_instance_query", side_effect=fake_query):
        _run_grouped(pending, all_instances, None, None, None, None, args, ablation, out)

    lines = [l for l in out.getvalue().splitlines() if l]
    written_ids = [json.loads(l)["instance_id"] for l in lines]
    expected_ids = [inst["instance_id"] for inst in all_instances]
    assert written_ids == expected_ids


def test_resume_filters_completed_before_grouping() -> None:
    """pending list already excludes completed IDs — grouping only sees pending."""
    all_instances = [
        _inst("owner/repoA", "abc", "A0"),
        _inst("owner/repoA", "abc", "A1"),  # "completed" — excluded from pending
        _inst("owner/repoA", "abc", "A2"),
    ]
    pending = [all_instances[0], all_instances[2]]  # A1 already done

    groups = _group_instances(
        [(i, inst) for i, inst in enumerate(all_instances) if inst in pending]
    )
    # Should still be a single group (same key), 2 instances.
    assert len(groups) == 1
    assert len(groups[0].instances) == 2
    instance_ids = [inst["instance_id"] for _, inst in groups[0].instances]
    assert "A1" not in instance_ids
