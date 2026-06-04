"""Unit tests for subgraph qualified-name expansion."""

from __future__ import annotations

from codegraph.core.graph.queries.subgraph import expand_qnames_with_file_nodes


def test_expand_qnames_adds_file_node_for_entities() -> None:
    qnames = [
        "src/pkg/tools.py::get_context",
        "src/pkg/tools.py::query_deps",
    ]
    expanded = expand_qnames_with_file_nodes(qnames)
    assert "src/pkg/tools.py::get_context" in expanded
    assert "src/pkg/tools.py" in expanded


def test_expand_qnames_uses_explicit_file_paths() -> None:
    expanded = expand_qnames_with_file_nodes(
        ["other.py::fn"],
        file_paths=["src/pkg/tools.py"],
    )
    assert "src/pkg/tools.py" in expanded
