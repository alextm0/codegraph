"""Unit tests for shortest_path_between query."""

from __future__ import annotations

from unittest.mock import MagicMock

from codegraph.core.graph.queries.path_tracing import shortest_path_between


def test_shortest_path_between_same_node():
    driver = MagicMock()
    result = shortest_path_between(driver, "a::foo", "a::foo")
    assert result["linked"] is True
    assert result["path_ids"] == ["a::foo"]
    assert result["hops"] == 0


def _mock_session(record):
    session = MagicMock()
    session.run.return_value.single.return_value = record
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    ctx.__exit__.return_value = None
    return ctx


def test_shortest_path_between_no_match():
    driver = MagicMock()
    driver.session.return_value = _mock_session(None)

    result = shortest_path_between(driver, "a::foo", "b::bar")
    assert result["linked"] is False
    assert result["path_ids"] == []


def test_shortest_path_between_found():
    driver = MagicMock()
    driver.session.return_value = _mock_session({
        "path_ids": ["a::foo", "a::bar", "b::baz"],
    })

    result = shortest_path_between(driver, "a::foo", "b::baz")
    assert result["linked"] is True
    assert len(result["path_ids"]) == 3
    assert result["hops"] == 2
