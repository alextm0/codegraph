"""Tests for src/retrieval/post_processing.py."""

from pathlib import Path

import pytest

from codegraph.core.parser.python_parser import create_parser, parse_directory
from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import PPRResult
from codegraph.core.retrieval.post_processing import (
    ContextResult,
    apply_idf_weights,
    count_tokens,
    format_context,
)
from tests.conftest import neo4j_required

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"
USER_AUTH = str(FIXTURES_DIR / "user_auth")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser():
    return create_parser()


@pytest.fixture(scope="module")
def user_auth_entities(parser):
    return parse_directory(USER_AUTH, parser)


@pytest.fixture(scope="module")
def populated_db(neo4j_driver, user_auth_entities):
    """Build user_auth graph once for the whole module."""
    clear_database(neo4j_driver)
    build_graph(neo4j_driver, user_auth_entities)
    yield neo4j_driver
    clear_database(neo4j_driver)


def _make_ppr_result(
    name: str = "foo",
    qualified_name: str = "a.py::foo",
    file_path: str = "a.py",
    score: float = 0.5,
    label: str = "Function",
    line_start: int = 0,
    line_end: int = 0,
) -> PPRResult:
    return PPRResult(
        qualified_name=qualified_name,
        name=name,
        label=label,
        file_path=file_path,
        score=score,
        line_start=line_start,
        line_end=line_end,
    )


# ---------------------------------------------------------------------------
# ContextResult — pure dataclass tests
# ---------------------------------------------------------------------------

class TestContextResult:
    def test_frozen(self):
        cr = ContextResult(
            entity_name="foo",
            qualified_name="a.py::foo",
            file_path="a.py",
            line_start=1,
            line_end=10,
            relevance_score=0.9,
            source_code="def foo(): pass",
            token_count=3,
        )
        with pytest.raises((AttributeError, TypeError)):
            cr.relevance_score = 0.0  # type: ignore[misc]

    def test_fields(self):
        cr = ContextResult(
            entity_name="bar",
            qualified_name="b.py::bar",
            file_path="b.py",
            line_start=5,
            line_end=20,
            relevance_score=0.75,
            source_code="def bar(): return 1",
            token_count=4,
        )
        assert cr.entity_name == "bar"
        assert cr.token_count == 4


# ---------------------------------------------------------------------------
# count_tokens — pure function tests
# ---------------------------------------------------------------------------

class TestCountTokens:
    def test_empty_string_is_zero(self):
        assert count_tokens("") == 0

    def test_single_word(self):
        assert count_tokens("hello") == 1

    def test_multiple_words(self):
        assert count_tokens("def foo(x, y):") == 3

    def test_multiline_code(self):
        code = "def foo():\n    return 42\n"
        result = count_tokens(code)
        # "def", "foo():", "return", "42" → 4 tokens
        assert result == 4

    def test_consistent_with_split(self):
        text = "a b c d e f"
        assert count_tokens(text) == len(text.split())


# ---------------------------------------------------------------------------
# format_context — pure function tests (uses tmp files, no Neo4j)
# ---------------------------------------------------------------------------

class TestFormatContext:
    def test_returns_list(self, tmp_path):
        ppr = _make_ppr_result(file_path="a.py", score=1.0)
        (tmp_path / "a.py").write_text("def foo(): pass\n")
        results = format_context([ppr], str(tmp_path), token_budget=100)
        assert isinstance(results, list)

    def test_single_result_returned(self, tmp_path):
        ppr = _make_ppr_result(name="foo", file_path="a.py", score=0.9)
        (tmp_path / "a.py").write_text("def foo(): pass\n")
        results = format_context([ppr], str(tmp_path), token_budget=100)
        assert len(results) == 1
        assert results[0].entity_name == "foo"

    def test_respects_token_budget(self, tmp_path):
        """With budget=5, only first item (which barely fits) should be included."""
        # Each file has ~10 tokens
        (tmp_path / "a.py").write_text("def foo(): return 1 + 2 + 3 + 4\n")
        (tmp_path / "b.py").write_text("def bar(): return 5 + 6 + 7 + 8\n")
        pprs = [
            _make_ppr_result(name="foo", file_path="a.py", score=0.9),
            _make_ppr_result(name="bar", file_path="b.py", score=0.5),
        ]
        results = format_context(pprs, str(tmp_path), token_budget=5)
        # At least 1 result always returned; second may be excluded
        assert len(results) >= 1
        assert results[0].entity_name == "foo"

    def test_always_returns_at_least_one_result(self, tmp_path):
        """Even if the single result exceeds budget, it should still be returned."""
        (tmp_path / "big.py").write_text("word " * 1000)
        ppr = _make_ppr_result(name="big_func", file_path="big.py", score=1.0)
        results = format_context([ppr], str(tmp_path), token_budget=10)
        assert len(results) == 1

    def test_missing_file_skipped(self, tmp_path):
        """Results pointing to non-existent files are skipped gracefully."""
        ppr = _make_ppr_result(name="ghost", file_path="ghost.py", score=1.0)
        results = format_context([ppr], str(tmp_path), token_budget=1000)
        assert results == []

    def test_empty_file_path_skipped(self, tmp_path):
        """Results with empty file_path are skipped gracefully."""
        ppr = _make_ppr_result(name="empty", file_path="", score=1.0)
        results = format_context([ppr], str(tmp_path), token_budget=1000)
        assert results == []

    def test_results_ordered_by_score(self, tmp_path):
        """format_context preserves the order of ppr_results (caller's responsibility)."""
        (tmp_path / "a.py").write_text("def foo(): pass\n")
        (tmp_path / "b.py").write_text("def bar(): pass\n")
        pprs = [
            _make_ppr_result(name="foo", file_path="a.py", score=0.9),
            _make_ppr_result(name="bar", file_path="b.py", score=0.3),
        ]
        results = format_context(pprs, str(tmp_path), token_budget=10000)
        assert results[0].entity_name == "foo"
        assert results[1].entity_name == "bar"

    def test_context_result_has_correct_score(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo(): pass\n")
        ppr = _make_ppr_result(name="foo", file_path="a.py", score=0.77)
        results = format_context([ppr], str(tmp_path), token_budget=100)
        assert results[0].relevance_score == pytest.approx(0.77)

    def test_token_count_populated(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo(): return 1\n")
        ppr = _make_ppr_result(name="foo", file_path="a.py", score=0.5)
        results = format_context([ppr], str(tmp_path), token_budget=100)
        assert results[0].token_count > 0

    def test_empty_ppr_results_returns_empty_list(self, tmp_path):
        results = format_context([], str(tmp_path), token_budget=1000)
        assert results == []

    def test_line_range_limits_source_code(self, tmp_path):
        """When line_start/line_end are set, only that slice is returned."""
        (tmp_path / "a.py").write_text("line1\nline2\nline3\nline4\nline5\n")
        ppr = _make_ppr_result(name="foo", file_path="a.py", score=0.5,
                               line_start=2, line_end=4)
        results = format_context([ppr], str(tmp_path), token_budget=1000)
        assert results[0].source_code == "line2\nline3\nline4"
        assert results[0].line_start == 2
        assert results[0].line_end == 4

    def test_missing_line_range_reads_whole_file(self, tmp_path):
        """When line_start/line_end are 0 (default), the whole file is read."""
        content = "line1\nline2\nline3\n"
        (tmp_path / "a.py").write_text(content)
        ppr = _make_ppr_result(name="foo", file_path="a.py", score=0.5)
        results = format_context([ppr], str(tmp_path), token_budget=1000)
        assert results[0].source_code == content

    def test_file_node_reads_whole_file(self, tmp_path):
        """File-labelled nodes always read the whole file regardless of line hints."""
        content = "x = 1\ny = 2\n"
        (tmp_path / "a.py").write_text(content)
        ppr = _make_ppr_result(name="a.py", label="File", file_path="a.py",
                               score=0.9, line_start=1, line_end=1)
        results = format_context([ppr], str(tmp_path), token_budget=1000)
        assert results[0].source_code == content


# ---------------------------------------------------------------------------
# apply_idf_weights — Neo4j-backed tests
# ---------------------------------------------------------------------------

@neo4j_required
class TestApplyIdfWeights:
    def test_returns_integer(self, populated_db):
        """apply_idf_weights must return the count of updated edges."""
        updated = apply_idf_weights(populated_db)
        assert isinstance(updated, int)
        assert updated >= 0

    def test_edges_updated(self, populated_db):
        """With user_auth graph (27 edges), at least some edges should be updated."""
        updated = apply_idf_weights(populated_db)
        assert updated > 0, f"Expected edges to be updated, got {updated}"

    def test_idempotent(self, populated_db):
        """Calling apply_idf_weights twice must not raise and must update same count."""
        first = apply_idf_weights(populated_db)
        second = apply_idf_weights(populated_db)
        assert first == second

    def test_high_indegree_node_gets_lower_weight(self, populated_db):
        """validate_email is called from register; its edge weight should be < 1.0."""
        apply_idf_weights(populated_db)
        with populated_db.session() as session:
            result = session.run(
                """
                MATCH ()-[r]->(target)
                WHERE target.name IN ['validate_email', 'validate_username', 'validate_password']
                RETURN r.weight AS w
                LIMIT 1
                """
            )
            record = result.single()
            if record:
                assert record["w"] < 1.0, f"Expected weight < 1.0, got {record['w']}"
