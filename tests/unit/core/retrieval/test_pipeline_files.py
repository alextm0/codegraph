"""Unit tests for file_paths_from_ppr_results."""

from codegraph.core.graph.ppr import PPRResult
from codegraph.core.retrieval.pipeline import file_paths_from_ppr_results


def test_first_entity_preserves_order() -> None:
    results = [
        PPRResult("a::x", "x", "Function", "b.py", 0.9),
        PPRResult("b::y", "y", "Function", "a.py", 0.8),
        PPRResult("c::z", "z", "Function", "b.py", 0.7),
    ]
    assert file_paths_from_ppr_results(results, rank_by="first_entity") == [
        "b.py",
        "a.py",
    ]


def test_max_score_ranks_by_best_entity() -> None:
    results = [
        PPRResult("a::x", "x", "Function", "b.py", 0.4),
        PPRResult("b::y", "y", "Function", "a.py", 0.9),
        PPRResult("c::z", "z", "Function", "b.py", 0.8),
    ]
    assert file_paths_from_ppr_results(results, rank_by="max_score") == [
        "a.py",
        "b.py",
    ]
