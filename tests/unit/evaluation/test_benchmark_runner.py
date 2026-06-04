"""Unit tests for evaluation.swe_bench_runner.BenchmarkRunner."""

import io
from unittest.mock import MagicMock, patch

import pytest

from evaluation.ablations import ABLATIONS
from evaluation.swe_bench_runner import (
    BenchmarkRunner,
    run_instance,
    run_instance_query,
    setup_group,
    zero_result,
)
from tests.unit.evaluation.conftest import make_instance


def _baseline_ablation():
    return next(a for a in ABLATIONS if a.name == "baseline")


def test_zero_result_defaults() -> None:
    result = zero_result("id-1", "owner/repo", ["a.py"], 42, 1.5)
    assert result["instance_id"] == "id-1"
    assert result["predicted_files"] == []
    assert result["recall_at_10"] == 0.0
    assert result["error"] is None
    assert result["total_nodes"] == 42


def test_zero_result_with_error() -> None:
    result = zero_result("id-1", "r", [], 0, 0.0, "clone failed")
    assert result["error"] == "clone failed"


def test_verify_db_empty_raises_when_nodes_exist() -> None:
    session = MagicMock()
    session.run.return_value.single.return_value = {"n": 1}
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session

    runner = BenchmarkRunner(driver, MagicMock(), None, "/cache", _baseline_ablation())
    with patch("evaluation.swe_bench_runner.clear_database"):
        with patch("evaluation.swe_bench_runner.build_graph", return_value={}):
            with patch("evaluation.swe_bench_runner.drop_projection"):
                with patch("evaluation.swe_bench_runner.clone_or_cache", return_value="/p"):
                    with patch("evaluation.swe_bench_runner.checkout_commit"):
                        with patch(
                            "evaluation.swe_bench_runner.parse_directory",
                            return_value=[],
                        ):
                            with pytest.raises(RuntimeError, match="not empty"):
                                runner.setup_group(("owner/r", "abc"))


def test_fetch_node_file_paths_empty() -> None:
    runner = BenchmarkRunner(MagicMock(), MagicMock(), None, "", _baseline_ablation())
    assert runner._fetch_node_file_paths([]) == []


def test_fetch_node_file_paths_returns_distinct_paths() -> None:
    session = MagicMock()
    session.run.return_value = [
        {"file_path": "a.py"},
        {"file_path": "b.py"},
    ]
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session

    runner = BenchmarkRunner(driver, MagicMock(), None, "", _baseline_ablation())
    paths = runner._fetch_node_file_paths([1, 2])
    assert paths == ["a.py", "b.py"]


@patch("evaluation.swe_bench_runner.run_core_retrieval")
@patch(
    "evaluation.swe_bench_runner.extract_gold_files",
    return_value=["gold.py"],
)
def test_run_instance_query_ppr_computes_metrics(
    _mock_gold: MagicMock,
    mock_core: MagicMock,
) -> None:
    from codegraph.core.graph.ppr import PPRResult

    mock_core.return_value = MagicMock(
        seeds=MagicMock(seeds={1: 1.0}),
        ppr_results=[
            PPRResult("a::f", "f", "Function", "gold.py", 1.0),
            PPRResult("b::g", "g", "Function", "other.py", 0.5),
        ],
    )

    session = MagicMock()
    session.run.return_value = [{"file_path": "seed.py"}]
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session

    instance = make_instance("owner/r", "abc", "inst-1")
    runner = BenchmarkRunner(driver, MagicMock(), None, "", _baseline_ablation(), "ppr")

    result = runner.run_instance_query(instance, total_nodes=100)

    assert result["error"] is None
    assert result["recall_at_10"] == 1.0
    assert result["predicted_files"] == ["gold.py", "other.py"]
    assert result["n_seeds"] == 1
    mock_core.assert_called_once()
    call_kwargs = mock_core.call_args.kwargs
    assert call_kwargs["graph_ready"] is True


@patch("evaluation.swe_bench_runner.run_core_retrieval", return_value=None)
def test_run_instance_query_no_seeds_returns_zero(mock_core: MagicMock) -> None:
    driver = MagicMock()
    instance = make_instance("owner/r", "abc", "inst-1")

    runner = BenchmarkRunner(driver, MagicMock(), None, "", _baseline_ablation(), "ppr")
    result = runner.run_instance_query(instance, total_nodes=10)

    assert result["predicted_files"] == []
    assert result["recall_at_10"] == 0.0
    assert result["n_seeds"] == 0


@patch("evaluation.baselines.RandomBaseline")
def test_run_instance_query_random_baseline(mock_cls: MagicMock) -> None:
    mock_cls.return_value.run.return_value = ["f1.py", "f2.py"]
    driver = MagicMock()
    instance = make_instance("owner/r", "abc", "inst-1")

    runner = BenchmarkRunner(driver, MagicMock(), None, "", _baseline_ablation(), "random")
    result = runner.run_instance_query(instance, total_nodes=5)

    assert result["predicted_files"] == ["f1.py", "f2.py"]
    assert result["n_seeds"] == 0


@patch("evaluation.swe_bench_runner.setup_group", return_value=(10, "/p", None, None))
@patch("evaluation.swe_bench_runner.run_instance_query")
def test_run_instance_delegates_setup_and_query(
    mock_query: MagicMock,
    mock_setup: MagicMock,
) -> None:
    instance = make_instance("owner/r", "commit", "x")
    mock_query.return_value = {"instance_id": "x", "error": None}

    result = run_instance(
        instance, MagicMock(), MagicMock(), MagicMock(), "/cache",
        _baseline_ablation(), "ppr",
    )

    mock_setup.assert_called_once()
    mock_query.assert_called_once()
    assert result["instance_id"] == "x"


@patch("evaluation.swe_bench_runner.BenchmarkRunner.setup_group")
def test_setup_group_module_wrapper(mock_setup: MagicMock) -> None:
    mock_setup.return_value = (1, "/p", None, None)
    out = setup_group(
        ("r", "c"), MagicMock(), MagicMock(), MagicMock(),
        "/cache", _baseline_ablation(), "ppr",
    )
    assert out == (1, "/p", None, None)
    mock_setup.assert_called_once()


@patch("evaluation.swe_bench_runner.BenchmarkRunner.run_instance_query")
def test_run_instance_query_module_wrapper(mock_query: MagicMock) -> None:
    mock_query.return_value = {"instance_id": "z"}
    instance = make_instance("r", "c", "z")
    result = run_instance_query(
        instance, MagicMock(), MagicMock(), 5, _baseline_ablation(), "ppr"
    )
    assert result["instance_id"] == "z"


def test_run_grouped_circuit_breaker() -> None:
    """Abort after consecutive setup failures without calling further groups."""
    from evaluation.swe_bench_runner import BenchmarkRunner

    instances = [
        make_instance(f"owner/repo{i}", f"c{i}", f"id{i}") for i in range(5)
    ]
    runner = BenchmarkRunner(
        MagicMock(), MagicMock(), MagicMock(), "/cache", _baseline_ablation()
    )
    out = io.StringIO()

    with patch(
        "evaluation.swe_bench_runner.setup_group",
        side_effect=RuntimeError("fail"),
    ):
        diag = runner.run_grouped(instances, instances, out, failure_streak_threshold=2)

    assert diag["n_groups"] == 5
    lines = [line for line in out.getvalue().splitlines() if line]
    assert len(lines) == 2
