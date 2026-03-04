"""Tests for src/graph/queries.py — read-only Cypher query functions."""

from pathlib import Path

import pytest

from codegraph.core.parser.python_parser import create_parser, parse_directory
from codegraph.core.graph.graph_builder import build_graph
from codegraph.core.graph.utils import normalize_path
from codegraph.core.graph.queries import (
    NodeInfo,
    count_nodes_by_label,
    count_edges_by_type,
    get_neighbors,
    get_file_contents,
    find_callers,
    find_callees,
    find_node_by_name,
    get_inheritance_chain,
)
from tests.conftest import neo4j_required

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"
USER_AUTH = str(FIXTURES_DIR / "user_auth")


@pytest.fixture(scope="module")
def parser():
    return create_parser()


@pytest.fixture(scope="module")
def user_auth_entities(parser):
    return parse_directory(USER_AUTH, parser)


@pytest.fixture(scope="module")
def qnames(user_auth_entities):
    """Map of 'Name' / 'ClassName.method' -> qualified_name, using actual normalized paths."""
    lookup: dict[str, str] = {}
    for fe in user_auth_entities:
        fp = normalize_path(fe.file_path)
        lookup[f"file:{fp}"] = fp  # file node itself
        for fn in fe.functions:
            lookup[fn.name] = f"{fp}::{fn.name}"
        for cls in fe.classes:
            lookup[cls.name] = f"{fp}::{cls.name}"
        for m in fe.methods:
            lookup[f"{m.class_name}.{m.name}"] = f"{fp}::{m.class_name}.{m.name}"
    return lookup


@pytest.fixture(scope="module")
def file_paths(user_auth_entities):
    """Map of short suffix (e.g. 'services/auth_service.py') -> full normalized path.

    Uses basename as key when unique; falls back to the last two path segments
    to disambiguate collisions (e.g. multiple ``__init__.py``).
    """
    lookup: dict[str, str] = {}
    for fe in user_auth_entities:
        fp = normalize_path(fe.file_path)
        parts = fp.split("/")
        # Always key by the last two path segments
        lookup["/".join(parts[-2:])] = fp
        # Key by basename only when there is no collision
        basename = parts[-1]
        if basename not in lookup:
            lookup[basename] = fp
        elif lookup[basename] != fp:
            # Collision: remove the ambiguous basename key so only the
            # two-segment key is usable for both paths.
            del lookup[basename]
    return lookup


@pytest.fixture(scope="module")
def populated_db(neo4j_driver, user_auth_entities):
    """Module-scoped fixture: build graph once and leave it for the whole module."""
    from codegraph.core.graph.graph_builder import clear_database
    clear_database(neo4j_driver)
    build_graph(neo4j_driver, user_auth_entities)
    yield neo4j_driver
    clear_database(neo4j_driver)


# ---------------------------------------------------------------------------
# NodeInfo
# ---------------------------------------------------------------------------

def test_node_info_is_frozen():
    """NodeInfo must be immutable."""
    node = NodeInfo(qualified_name="a::b", name="b", label="Function", file_path="a.py")
    with pytest.raises((AttributeError, TypeError)):
        node.name = "c"  # type: ignore[misc]


def test_node_info_fields():
    """NodeInfo stores all four fields correctly."""
    node = NodeInfo(qualified_name="a::b", name="b", label="Class", file_path="a.py")
    assert node.qualified_name == "a::b"
    assert node.name == "b"
    assert node.label == "Class"
    assert node.file_path == "a.py"


# ---------------------------------------------------------------------------
# count_nodes_by_label
# ---------------------------------------------------------------------------

@neo4j_required
def test_count_nodes_by_label_returns_dict(populated_db):
    """count_nodes_by_label returns a non-empty dict."""
    counts = count_nodes_by_label(populated_db)
    assert isinstance(counts, dict)
    assert len(counts) > 0


@neo4j_required
def test_count_nodes_by_label_known_labels(populated_db):
    """Expected labels are present in the count dict."""
    counts = count_nodes_by_label(populated_db)
    for label in ("File", "Class", "Method", "Function"):
        assert label in counts, f"Expected label '{label}' missing from counts"


# ---------------------------------------------------------------------------
# count_edges_by_type
# ---------------------------------------------------------------------------

@neo4j_required
def test_count_edges_by_type_returns_dict(populated_db):
    """count_edges_by_type returns a non-empty dict."""
    counts = count_edges_by_type(populated_db)
    assert isinstance(counts, dict)
    assert len(counts) > 0


@neo4j_required
def test_count_edges_by_type_known_types(populated_db):
    """Expected relationship types are present."""
    counts = count_edges_by_type(populated_db)
    for rel in ("CONTAINS", "CALLS", "INHERITS_FROM"):
        assert rel in counts, f"Expected relationship '{rel}' missing"


# ---------------------------------------------------------------------------
# get_neighbors
# ---------------------------------------------------------------------------

@neo4j_required
def test_get_neighbors_returns_list(populated_db, qnames):
    """get_neighbors returns a list (possibly empty)."""
    results = get_neighbors(populated_db, qnames["AuthService"])
    assert isinstance(results, list)


@neo4j_required
def test_get_neighbors_class_has_neighbors(populated_db, qnames):
    """AuthService class node must have at least one neighbor (its methods)."""
    results = get_neighbors(populated_db, qnames["AuthService"])
    assert len(results) > 0


@neo4j_required
def test_get_neighbors_returns_node_info_objects(populated_db, qnames):
    """All returned items must be NodeInfo instances."""
    results = get_neighbors(populated_db, qnames["AuthService"])
    for item in results:
        assert isinstance(item, NodeInfo)


# ---------------------------------------------------------------------------
# get_file_contents
# ---------------------------------------------------------------------------

@neo4j_required
def test_get_file_contents_returns_entities(populated_db, file_paths):
    """auth_service.py file node must contain AuthService."""
    fp = file_paths["auth_service.py"]
    results = get_file_contents(populated_db, fp)
    names = {r.name for r in results}
    assert "AuthService" in names


@neo4j_required
def test_get_file_contents_returns_node_info(populated_db, file_paths):
    """All results must be NodeInfo instances."""
    fp = file_paths["auth_service.py"]
    results = get_file_contents(populated_db, fp)
    for item in results:
        assert isinstance(item, NodeInfo)


# ---------------------------------------------------------------------------
# find_callers / find_callees
# ---------------------------------------------------------------------------

@neo4j_required
def test_find_callees_for_register(populated_db, qnames):
    """AuthService.register calls validate_* functions -> callees must include validators."""
    qname = qnames["AuthService.register"]
    callees = find_callees(populated_db, qname)
    callee_names = {c.name for c in callees}
    assert callee_names & {"validate_email", "validate_username", "validate_password"}


@neo4j_required
def test_find_callers_for_validator(populated_db, qnames):
    """validate_email is called by AuthService.register -> must appear in callers."""
    qname = qnames["validate_email"]
    callers = find_callers(populated_db, qname)
    caller_names = {c.name for c in callers}
    assert "register" in caller_names


@neo4j_required
def test_find_callees_returns_node_info(populated_db, qnames):
    """All callee results must be NodeInfo instances."""
    qname = qnames["AuthService.register"]
    for item in find_callees(populated_db, qname):
        assert isinstance(item, NodeInfo)


# ---------------------------------------------------------------------------
# find_node_by_name
# ---------------------------------------------------------------------------

@neo4j_required
def test_find_node_by_name_finds_class(populated_db):
    """Searching by name 'AuthService' must return at least one result."""
    results = find_node_by_name(populated_db, "AuthService")
    assert len(results) >= 1
    assert any(r.label == "Class" for r in results)


@neo4j_required
def test_find_node_by_name_unknown_returns_empty(populated_db):
    """Searching for a name that doesn't exist must return an empty list."""
    results = find_node_by_name(populated_db, "NonExistentNodeXYZ")
    assert results == []


# ---------------------------------------------------------------------------
# get_inheritance_chain
# ---------------------------------------------------------------------------

@neo4j_required
def test_get_inheritance_chain_user_inherits_base_model(populated_db, qnames):
    """User inherits from BaseModel -> chain must include BaseModel."""
    qname = qnames["User"]
    chain = get_inheritance_chain(populated_db, qname)
    names = {n.name for n in chain}
    assert "BaseModel" in names


@neo4j_required
def test_get_inheritance_chain_base_model_is_empty(populated_db, qnames):
    """BaseModel has no parents -> chain must be empty."""
    qname = qnames["BaseModel"]
    chain = get_inheritance_chain(populated_db, qname)
    assert chain == []
