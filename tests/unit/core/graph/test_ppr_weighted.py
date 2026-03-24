"""Unit tests for weighted PPR (per-seed linear combination).

These tests mock GDS calls and verify the mathematical properties of the
weighted combination without requiring a running Neo4j instance.
"""

from unittest.mock import MagicMock, patch

import pytest

from codegraph.core.graph.ppr import (
    PPRConfig,
    run_ppr_from_node_ids,
    run_ppr_weighted,
)

_MODULE = "codegraph.core.graph.ppr"

# Reusable mock property map returned by _fetch_all_node_properties
_PROPS = {
    10: {
        "qualified_name": "mod.py::foo",
        "name": "foo",
        "label": "Function",
        "file_path": "mod.py",
        "line_start": 1,
        "line_end": 5,
    },
    20: {
        "qualified_name": "mod.py::bar",
        "name": "bar",
        "label": "Function",
        "file_path": "mod.py",
        "line_start": 10,
        "line_end": 15,
    },
    30: {
        "qualified_name": "other.py::baz",
        "name": "baz",
        "label": "Function",
        "file_path": "other.py",
        "line_start": 1,
        "line_end": 3,
    },
}


def _mock_fetch(driver, node_ids):
    """Return props only for requested node_ids."""
    return {nid: _PROPS[nid] for nid in node_ids if nid in _PROPS}


# ---------------------------------------------------------------------------
# PPRConfig.retrieval_mode tests
# ---------------------------------------------------------------------------

class TestPPRConfigRetrievalMode:
    def test_default_is_weighted(self) -> None:
        assert PPRConfig().retrieval_mode == "weighted"

    def test_explicit_uniform(self) -> None:
        assert PPRConfig(retrieval_mode="uniform").retrieval_mode == "uniform"

    def test_explicit_weighted(self) -> None:
        assert PPRConfig(retrieval_mode="weighted").retrieval_mode == "weighted"


# ---------------------------------------------------------------------------
# run_ppr_weighted tests
# ---------------------------------------------------------------------------

class TestRunPPRWeighted:
    """Tests for run_ppr_weighted() using mocked _run_ppr_single_seed."""

    @patch(f"{_MODULE}._fetch_all_node_properties", side_effect=_mock_fetch)
    @patch(f"{_MODULE}._run_ppr_single_seed")
    def test_single_seed(self, mock_single: MagicMock, mock_fetch: MagicMock) -> None:
        """Single seed: output scores equal the single-seed PPR scores."""
        mock_single.return_value = {10: 0.5, 20: 0.3, 30: 0.1}

        gds = MagicMock()
        driver = MagicMock()
        config = PPRConfig(top_k=3)

        results = run_ppr_weighted(gds, driver, {1: 1.0}, config)

        assert len(results) == 3
        assert results[0].score == pytest.approx(0.5)
        assert results[1].score == pytest.approx(0.3)
        assert results[2].score == pytest.approx(0.1)
        mock_single.assert_called_once_with(gds, 1, config)

    @patch(f"{_MODULE}._fetch_all_node_properties", side_effect=_mock_fetch)
    @patch(f"{_MODULE}._run_ppr_single_seed")
    def test_weight_normalization(self, mock_single: MagicMock, mock_fetch: MagicMock) -> None:
        """Weights {1: 2.0, 2: 3.0} normalize to {1: 0.4, 2: 0.6}."""
        # Seed 1 returns: node 10 → 1.0, node 20 → 0.5
        # Seed 2 returns: node 10 → 0.0, node 20 → 1.0, node 30 → 0.5
        def single_seed_side_effect(gds, seed_id, config):
            if seed_id == 1:
                return {10: 1.0, 20: 0.5}
            return {10: 0.0, 20: 1.0, 30: 0.5}

        mock_single.side_effect = single_seed_side_effect

        gds = MagicMock()
        driver = MagicMock()
        config = PPRConfig(top_k=10)

        results = run_ppr_weighted(gds, driver, {1: 2.0, 2: 3.0}, config)

        scores = {r.name: r.score for r in results}
        # node 10: 0.4 * 1.0 + 0.6 * 0.0 = 0.4
        assert scores["foo"] == pytest.approx(0.4)
        # node 20: 0.4 * 0.5 + 0.6 * 1.0 = 0.8
        assert scores["bar"] == pytest.approx(0.8)
        # node 30: 0.4 * 0.0 + 0.6 * 0.5 = 0.3
        assert scores["baz"] == pytest.approx(0.3)

    @patch(f"{_MODULE}._fetch_all_node_properties", side_effect=_mock_fetch)
    @patch(f"{_MODULE}._run_ppr_single_seed")
    def test_top_k_limits_results(self, mock_single: MagicMock, mock_fetch: MagicMock) -> None:
        """top_k=2 returns only the 2 highest-scored nodes."""
        mock_single.return_value = {10: 0.5, 20: 0.3, 30: 0.1}

        gds = MagicMock()
        driver = MagicMock()
        config = PPRConfig(top_k=2)

        results = run_ppr_weighted(gds, driver, {1: 1.0}, config)
        assert len(results) == 2
        assert results[0].name == "foo"
        assert results[1].name == "bar"

    def test_empty_seeds_raises(self) -> None:
        gds = MagicMock()
        driver = MagicMock()
        with pytest.raises(ValueError, match="non-empty"):
            run_ppr_weighted(gds, driver, {}, PPRConfig())

    def test_zero_total_weight_raises(self) -> None:
        gds = MagicMock()
        driver = MagicMock()
        with pytest.raises(ValueError, match="positive total weight"):
            run_ppr_weighted(gds, driver, {1: 0.0, 2: 0.0}, PPRConfig())


# ---------------------------------------------------------------------------
# run_ppr_from_node_ids dispatcher tests
# ---------------------------------------------------------------------------

class TestDispatcher:
    """Tests that run_ppr_from_node_ids routes to the correct implementation."""

    @patch(f"{_MODULE}._run_ppr_uniform")
    @patch(f"{_MODULE}.run_ppr_weighted")
    def test_routes_weighted(self, mock_weighted: MagicMock, mock_uniform: MagicMock) -> None:
        mock_weighted.return_value = []
        gds = MagicMock()
        driver = MagicMock()
        config = PPRConfig(retrieval_mode="weighted")

        run_ppr_from_node_ids(gds, driver, {1: 0.5}, config)

        mock_weighted.assert_called_once_with(gds, driver, {1: 0.5}, config)
        mock_uniform.assert_not_called()

    @patch(f"{_MODULE}._run_ppr_uniform")
    @patch(f"{_MODULE}.run_ppr_weighted")
    def test_routes_uniform(self, mock_weighted: MagicMock, mock_uniform: MagicMock) -> None:
        mock_uniform.return_value = []
        gds = MagicMock()
        driver = MagicMock()
        config = PPRConfig(retrieval_mode="uniform")

        run_ppr_from_node_ids(gds, driver, {1: 0.5}, config)

        mock_uniform.assert_called_once_with(gds, driver, {1: 0.5}, config)
        mock_weighted.assert_not_called()

    @patch(f"{_MODULE}._run_ppr_uniform")
    @patch(f"{_MODULE}.run_ppr_weighted")
    def test_empty_seeds_returns_empty(self, mock_weighted: MagicMock, mock_uniform: MagicMock) -> None:
        gds = MagicMock()
        driver = MagicMock()

        result = run_ppr_from_node_ids(gds, driver, {}, PPRConfig())

        assert result == []
        mock_weighted.assert_not_called()
        mock_uniform.assert_not_called()
