"""Unit tests for explanation DTO and seed provenance."""

from unittest.mock import MagicMock, patch

from codegraph.core.graph.ppr import PPRResult
from codegraph.core.retrieval.explanations import (
    ExplainedResult,
    _contribution_tag,
    build_explained_results,
)
from codegraph.core.retrieval.pipeline import RawRetrievalResult
from codegraph.core.retrieval.seed_selection import PersonalizationVector


def _core_result() -> RawRetrievalResult:
    seeds = PersonalizationVector(
        seeds={1: 0.6, 2: 0.4},
        metadata={
            1: {"qname": "auth.py::login", "source": "entity_match"},
            2: {"qname": "auth.py", "source": "bm25"},
        },
    )
    ppr = [
        PPRResult(
            qualified_name="auth.py::logout",
            name="logout",
            label="Function",
            file_path="auth.py",
            score=0.8,
            line_start=10,
            line_end=20,
        )
    ]
    return RawRetrievalResult(seeds=seeds, ppr_results=ppr)


class TestContributionTag:
    def test_direct_entity_is_lexical(self):
        assert _contribution_tag("direct seed", ("entity_match",)) == "lexical"

    def test_graph_path_is_graph(self):
        assert _contribution_tag("A -[CALLS]-> B", ()) == "graph"

    def test_mixed_is_both(self):
        assert _contribution_tag("A -[CALLS]-> B", ("bm25",)) == "both"


class TestBuildExplainedResults:
    def test_uses_metadata_source(self):
        driver = MagicMock()
        traced = {
            "auth.py::logout": {
                "path_str": "login -[CALLS]-> logout",
                "path_ids": ["auth.py::login", "auth.py::logout"],
            }
        }
        with patch(
            "codegraph.core.retrieval.explanations.batch_trace_paths",
            return_value=traced,
        ):
            explained = build_explained_results(driver, _core_result(), top_k=5)

        assert len(explained) == 1
        assert explained[0].seed_sources == ("entity_match",)
        assert explained[0].contribution == "both"
        assert isinstance(explained[0], ExplainedResult)
