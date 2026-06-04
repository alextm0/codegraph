"""End-to-end orchestration tests for grouped SWE-bench runner output order."""

import io
import json
from unittest.mock import MagicMock, patch

from evaluation.swe_bench_runner import _run_grouped
from tests.unit.evaluation.conftest import make_instance


def test_output_order_preserved_end_to_end() -> None:
    """Grouped mode writes results in original dataset order."""
    all_instances = [
        make_instance("owner/repoA", "abc", f"A{i}") for i in range(3)
    ] + [
        make_instance("owner/repoB", "def", f"B{i}") for i in range(2)
    ]
    pending = all_instances[:]

    def fake_setup(group_key, driver, gds, parser, cache_dir, ablation, retriever):
        return 10, "/fake/path", None, None

    def fake_query(instance, *args, **kwargs):
        iid = instance["instance_id"]
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

    with (
        patch("evaluation.swe_bench_runner.setup_group", side_effect=fake_setup),
        patch("evaluation.swe_bench_runner.run_instance_query", side_effect=fake_query),
    ):
        _run_grouped(pending, all_instances, None, None, None, None, args, ablation, out)

    lines = [line for line in out.getvalue().splitlines() if line]
    written_ids = [json.loads(line)["instance_id"] for line in lines]
    expected_ids = [inst["instance_id"] for inst in all_instances]
    assert written_ids == expected_ids


def test_resume_filters_completed_before_grouping() -> None:
    """Grouping only sees pending instances (completed IDs excluded upstream)."""
    from evaluation.dataset import group_instances

    all_instances = [
        make_instance("owner/repoA", "abc", "A0"),
        make_instance("owner/repoA", "abc", "A1"),
        make_instance("owner/repoA", "abc", "A2"),
    ]
    pending = [all_instances[0], all_instances[2]]

    groups = group_instances(
        [(i, inst) for i, inst in enumerate(all_instances) if inst in pending]
    )
    assert len(groups) == 1
    assert len(groups[0].instances) == 2
    instance_ids = [inst["instance_id"] for _, inst in groups[0].instances]
    assert "A1" not in instance_ids
