"""Integration tests for the grouped SWE-bench runner.

These tests monkeypatch setup_group and run_instance_query (no real Neo4j or
GitHub access needed) and verify the orchestration logic of _run_grouped().
"""

import io
import json
from unittest.mock import MagicMock, call, patch

import pytest

from evaluation.swe_bench_runner import (
    InstanceGroup,
    _group_instances,
    _run_grouped,
    _zero_result,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _inst(repo: str, base_commit: str, instance_id: str) -> dict:
    return {
        "repo": repo,
        "base_commit": base_commit,
        "instance_id": instance_id,
        "problem_statement": "fix something",
        "patch": "",
    }


def _make_args(retriever: str = "ppr", cache_dir: str = "/cache", threshold: int = 5):
    args = MagicMock()
    args.retriever = retriever
    args.cache_dir = cache_dir
    args.failure_streak_threshold = threshold
    return args


def _fake_query_result(instance: dict, total_nodes: int = 10) -> dict:
    return {
        "instance_id": instance["instance_id"],
        "repo": instance["repo"],
        "gold_files": [],
        "predicted_files": [],
        "recall_at_5": 0.0,
        "recall_at_10": 0.0,
        "mrr": 0.0,
        "n_seeds": 0,
        "total_nodes": total_nodes,
        "elapsed_seconds": 0.0,
        "error": None,
    }


# ── Test 1: setup_group called once per group, not per instance ───────────────

def test_setup_group_called_once_per_group() -> None:
    all_instances = [
        _inst("owner/repoA", "abc", "A0"),
        _inst("owner/repoA", "abc", "A1"),
        _inst("owner/repoB", "def", "B0"),
    ]
    pending = all_instances[:]
    args = _make_args()
    ablation = MagicMock()
    out = io.StringIO()

    setup_calls: list[tuple] = []

    def fake_setup(group_key, driver, gds, parser, cache_dir, ablation, retriever):
        setup_calls.append(group_key)
        return 10, "/fake"

    def fake_query(instance, driver, gds, total_nodes, ablation, retriever):
        return _fake_query_result(instance)

    with patch("evaluation.swe_bench_runner.setup_group", side_effect=fake_setup), \
         patch("evaluation.swe_bench_runner.run_instance_query", side_effect=fake_query):
        _run_grouped(pending, all_instances, None, None, None, args, ablation, out)

    # setup_group should have been called exactly twice (once per group key).
    assert len(setup_calls) == 2
    assert ("owner/repoA", "abc") in setup_calls
    assert ("owner/repoB", "def") in setup_calls


# ── Test 2: group setup failure → all instances in group get error results ────

def test_group_setup_failure_error_results_other_groups_unaffected() -> None:
    all_instances = [
        _inst("owner/repoA", "abc", "A0"),
        _inst("owner/repoA", "abc", "A1"),
        _inst("owner/repoB", "def", "B0"),
    ]
    pending = all_instances[:]
    args = _make_args()
    ablation = MagicMock()
    out = io.StringIO()

    def fake_setup(group_key, driver, gds, parser, cache_dir, ablation, retriever):
        if group_key[0] == "owner/repoA":
            raise RuntimeError("clone failed")
        return 10, "/fake"

    def fake_query(instance, driver, gds, total_nodes, ablation, retriever):
        return _fake_query_result(instance)

    with patch("evaluation.swe_bench_runner.setup_group", side_effect=fake_setup), \
         patch("evaluation.swe_bench_runner.run_instance_query", side_effect=fake_query):
        _run_grouped(pending, all_instances, None, None, None, args, ablation, out)

    lines = [l for l in out.getvalue().splitlines() if l]
    results = {json.loads(l)["instance_id"]: json.loads(l) for l in lines}

    assert len(results) == 3
    assert results["A0"]["error"] is not None
    assert results["A1"]["error"] is not None
    assert results["B0"]["error"] is None


# ── Test 3: --no-grouping vs --grouping repo_commit produce identical metrics ─

def test_no_grouping_vs_grouped_identical_metrics() -> None:
    """run_instance() (no-grouping) and _run_grouped() should produce same results."""
    from evaluation.swe_bench_runner import run_instance

    all_instances = [
        _inst("owner/repoA", "abc", "A0"),
        _inst("owner/repoB", "def", "B0"),
    ]
    pending = all_instances[:]
    ablation = MagicMock()

    # Grouped output
    args = _make_args()
    out_grouped = io.StringIO()

    def fake_setup(group_key, *a, **kw):
        return 42, "/fake"

    def fake_query(instance, *a, **kw):
        return _fake_query_result(instance, total_nodes=42)

    with patch("evaluation.swe_bench_runner.setup_group", side_effect=fake_setup), \
         patch("evaluation.swe_bench_runner.run_instance_query", side_effect=fake_query):
        _run_grouped(pending, all_instances, None, None, None, args, ablation, out_grouped)

    grouped_lines = [l for l in out_grouped.getvalue().splitlines() if l]
    grouped_results = sorted(
        [json.loads(l) for l in grouped_lines], key=lambda r: r["instance_id"]
    )

    # No-grouping output using run_instance() with same mocked setup+query
    no_group_results = []
    with patch("evaluation.swe_bench_runner.setup_group", side_effect=fake_setup), \
         patch("evaluation.swe_bench_runner.run_instance_query", side_effect=fake_query):
        for inst in all_instances:
            no_group_results.append(
                run_instance(inst, None, None, None, "/cache", ablation, "ppr")
            )
    no_group_results.sort(key=lambda r: r["instance_id"])

    for g, ng in zip(grouped_results, no_group_results):
        assert g["instance_id"] == ng["instance_id"]
        assert g["recall_at_5"] == ng["recall_at_5"]
        assert g["recall_at_10"] == ng["recall_at_10"]
        assert g["mrr"] == ng["mrr"]
        assert g["n_seeds"] == ng["n_seeds"]


# ── Test 4: circuit breaker triggers after N consecutive setup failures ────────

def test_circuit_breaker_triggers_after_consecutive_failures() -> None:
    # 6 groups, all fail — circuit breaker at threshold=3 should stop after 3.
    n_groups = 6
    all_instances = [
        _inst(f"owner/repo{i}", f"commit{i}", f"id{i}")
        for i in range(n_groups)
    ]
    pending = all_instances[:]
    args = _make_args(threshold=3)
    ablation = MagicMock()
    out = io.StringIO()

    setup_call_count = 0

    def fake_setup(group_key, *a, **kw):
        nonlocal setup_call_count
        setup_call_count += 1
        raise RuntimeError("setup failed")

    def fake_query(instance, *a, **kw):
        return _fake_query_result(instance)

    with patch("evaluation.swe_bench_runner.setup_group", side_effect=fake_setup), \
         patch("evaluation.swe_bench_runner.run_instance_query", side_effect=fake_query):
        _run_grouped(pending, all_instances, None, None, None, args, ablation, out)

    # Should have stopped after 3 consecutive failures.
    assert setup_call_count == 3


def test_circuit_breaker_resets_on_success() -> None:
    """A successful setup resets the consecutive failure counter."""
    all_instances = [
        _inst("owner/repoFail1", "c1", "F1"),
        _inst("owner/repoOK", "c2", "OK"),
        _inst("owner/repoFail2", "c3", "F2"),
        _inst("owner/repoFail3", "c4", "F3"),
        _inst("owner/repoFail4", "c5", "F4"),
    ]
    pending = all_instances[:]
    args = _make_args(threshold=3)
    ablation = MagicMock()
    out = io.StringIO()

    def fake_setup(group_key, *a, **kw):
        if group_key[0] == "owner/repoOK":
            return 10, "/fake"
        raise RuntimeError("setup failed")

    def fake_query(instance, *a, **kw):
        return _fake_query_result(instance)

    with patch("evaluation.swe_bench_runner.setup_group", side_effect=fake_setup), \
         patch("evaluation.swe_bench_runner.run_instance_query", side_effect=fake_query):
        _run_grouped(pending, all_instances, None, None, None, args, ablation, out)

    lines = [l for l in out.getvalue().splitlines() if l]
    results = {json.loads(l)["instance_id"]: json.loads(l) for l in lines}

    # F1 fails (streak=1), OK succeeds (resets), F2/F3/F4 fail (streak hits 3 → abort at F4).
    assert results["F1"]["error"] is not None
    assert results["OK"]["error"] is None
    # F2 and F3 must be processed (streak 1,2) before circuit breaker fires at F4.
    assert results["F2"]["error"] is not None
    assert results["F3"]["error"] is not None
    # After streak of 3 (F2,F3,F4) the loop breaks — F4 result is in buffer flushed via force_all.
    assert results["F4"]["error"] is not None
