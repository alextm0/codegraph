"""Unit tests for post_processing.py helpers that don't require Neo4j."""

import pytest
from codegraph.core.graph.ppr import PPRResult
from codegraph.core.retrieval.post_processing import (
    apply_directory_colocation_bonus,
    _directory_key,
)


def _make_result(qname: str, file_path: str, score: float) -> PPRResult:
    return PPRResult(
        qualified_name=qname,
        name=qname.split("::")[-1],
        label="Function",
        file_path=file_path,
        score=score,
    )


class TestApplyDirectoryColocationBonus:
    def test_clustered_results_get_boosted(self):
        results = [
            _make_result("a::f1", "django/db/models/query.py", 0.8),
            _make_result("a::f2", "django/db/models/sql/compiler.py", 0.7),
            _make_result("b::f3", "astropy/modeling/separable.py", 0.6),
        ]
        boosted = apply_directory_colocation_bonus(results, depth=2, min_cluster_size=2, bonus=1.2)
        # django/db has 2 results → both boosted
        score_map = {r.qualified_name: r.score for r in boosted}
        assert score_map["a::f1"] == pytest.approx(0.8 * 1.2)
        assert score_map["a::f2"] == pytest.approx(0.7 * 1.2)
        # astropy not boosted
        assert score_map["b::f3"] == pytest.approx(0.6)

    def test_no_cluster_no_change(self):
        results = [
            _make_result("a::f1", "django/db/models/query.py", 0.8),
            _make_result("b::f2", "astropy/modeling/separable.py", 0.7),
            _make_result("c::f3", "sympy/printing/latex.py", 0.6),
        ]
        boosted = apply_directory_colocation_bonus(results, depth=2, min_cluster_size=2)
        # All in different dirs → no change
        assert [r.score for r in boosted] == pytest.approx([0.8, 0.7, 0.6])

    def test_resorting_after_boost(self):
        results = [
            _make_result("a::f1", "other/module.py", 0.9),  # not clustered
            _make_result("b::f2", "django/db/models/query.py", 0.5),
            _make_result("c::f3", "django/db/models/sql/compiler.py", 0.4),
        ]
        boosted = apply_directory_colocation_bonus(results, depth=2, min_cluster_size=2, bonus=1.2)
        # After boost: django/db results = 0.6 and 0.48, other = 0.9
        assert boosted[0].qualified_name == "a::f1"  # 0.9 still first
        assert boosted[1].qualified_name == "b::f2"  # 0.6 second
        assert boosted[2].qualified_name == "c::f3"  # 0.48 third

    def test_empty_input(self):
        assert apply_directory_colocation_bonus([]) == []

    def test_single_result(self):
        results = [_make_result("a::f1", "django/db/models/query.py", 0.8)]
        # Only 1 result → no cluster possible
        result = apply_directory_colocation_bonus(results, min_cluster_size=2)
        assert result[0].score == pytest.approx(0.8)

    def test_empty_file_path_not_clustered(self):
        results = [
            _make_result("a::f1", "", 0.8),
            _make_result("b::f2", "", 0.7),
        ]
        # Empty file paths are excluded from dir counting (if ppr.file_path guard),
        # so no cluster forms and scores are unchanged.
        boosted = apply_directory_colocation_bonus(results, depth=2, min_cluster_size=2, bonus=1.5)
        score_map = {r.qualified_name: r.score for r in boosted}
        assert score_map["a::f1"] == pytest.approx(0.8)
        assert score_map["b::f2"] == pytest.approx(0.7)


class TestDirectoryKey:
    def test_depth_2(self):
        assert _directory_key("django/db/models/sql/compiler.py", 2) == "django/db"

    def test_short_path(self):
        assert _directory_key("module.py", 2) == "module.py"

    def test_windows_backslash(self):
        assert _directory_key("django\\db\\models\\compiler.py", 2) == "django/db"

    def test_depth_1(self):
        assert _directory_key("django/db/models/compiler.py", 1) == "django"

    def test_exact_depth_match(self):
        assert _directory_key("a/b.py", 2) == "a/b.py"
