"""Unit tests for post_processing.py helpers that don't require Neo4j."""

import pytest
from codegraph.core.graph.ppr import PPRResult
from codegraph.core.retrieval.post_processing import count_tokens, _deduplicate_file_entities


def _make_result(qname: str, file_path: str, score: float, label: str = "Function") -> PPRResult:
    return PPRResult(
        qualified_name=qname,
        name=qname.split("::")[-1],
        label=label,
        file_path=file_path,
        score=score,
    )


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_non_empty(self):
        assert count_tokens("def foo(): pass") > 0

    def test_longer_is_more_tokens(self):
        short = count_tokens("x = 1")
        long = count_tokens("x = 1\n" * 20)
        assert long > short


class TestDeduplicateFileEntities:
    def test_keeps_file_when_fewer_than_two_sub_entities(self):
        results = [
            _make_result("a.py", "a.py", 0.9, label="File"),
            _make_result("a.py::foo", "a.py", 0.8),
        ]
        deduped = _deduplicate_file_entities(results)
        assert len(deduped) == 2

    def test_drops_file_when_two_or_more_sub_entities(self):
        results = [
            _make_result("a.py", "a.py", 0.9, label="File"),
            _make_result("a.py::foo", "a.py", 0.8),
            _make_result("a.py::bar", "a.py", 0.7),
        ]
        deduped = _deduplicate_file_entities(results)
        qnames = [r.qualified_name for r in deduped]
        assert "a.py" not in qnames
        assert "a.py::foo" in qnames
        assert "a.py::bar" in qnames

    def test_keeps_file_from_other_module_untouched(self):
        results = [
            _make_result("a.py", "a.py", 0.9, label="File"),
            _make_result("a.py::foo", "a.py", 0.8),
            _make_result("a.py::bar", "a.py", 0.7),
            _make_result("b.py", "b.py", 0.6, label="File"),
        ]
        deduped = _deduplicate_file_entities(results)
        qnames = [r.qualified_name for r in deduped]
        assert "a.py" not in qnames
        assert "b.py" in qnames

    def test_empty_input(self):
        assert _deduplicate_file_entities([]) == []
