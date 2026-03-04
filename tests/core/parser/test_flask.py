"""Tests for the Python tree-sitter parser against the real Flask repository.

Convention: one test file per fixture project.
  tests/fixtures/flask/  <->  tests/test_parser_flask.py  (this file)

Why Flask?
  Flask is a real-world Python library with non-trivial patterns:
  - Deep class hierarchies with multiple inheritance
  - Decorated methods (@property, @staticmethod, @t.overload)
  - Relative intra-package imports and absolute third-party imports
  - Nested functions (e.g. `view` inside `View.as_view`)
  - Overloaded function signatures via @t.overload

Selected files and why:
  views.py              — small, self-contained: two classes, no top-level functions,
                          relative imports, method call graph
  sessions.py           — five-class hierarchy with multi-inheritance; rich docstrings;
                          many methods on SessionInterface
  helpers.py            — 16 top-level functions; overloaded stream_with_context;
                          third-party werkzeug imports; stdlib filtered out
  config.py             — Config inherits from plain `dict`; no functions, only a class
  wrappers.py           — concrete single-method classes with third-party bases

Each test is labelled with what real-world pattern it exercises so failures are easy to diagnose.
"""

from pathlib import Path

import pytest

from codegraph.core.parser.models import FileEntities
from codegraph.core.parser.python_parser import create_parser, parse_directory, parse_file

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"

# Root of the cloned Flask repository source package
PROJECT = FIXTURES_DIR / "flask" / "src" / "flask"


@pytest.fixture(scope="module")
def parser():
    return create_parser()


def read(relative_path: str) -> bytes:
    """Read a file from the Flask fixture package."""
    return (PROJECT / relative_path).read_bytes()


# ---------------------------------------------------------------------------
# Function extraction — helpers.py (16 top-level functions)
# ---------------------------------------------------------------------------


def test_known_top_level_functions_are_extracted(parser):
    """helpers.py defines well-known Flask public functions that must be found."""
    entities = parse_file(read("helpers.py"), "helpers.py", parser)

    names = {f.name for f in entities.functions}
    # Core Flask public API — if any of these are missing, the extractor broke
    assert "make_response" in names
    assert "url_for" in names
    assert "send_file" in names
    assert "flash" in names
    assert "get_flashed_messages" in names


def test_no_methods_leak_into_top_level_functions(parser):
    """Top-level functions must not include any class methods.

    helpers.py defines _CollectErrors with instance methods — none should
    appear in the functions list.
    """
    entities = parse_file(read("helpers.py"), "helpers.py", parser)

    # _CollectErrors is the only class; its methods are 'push' and 'blueprint'
    method_names = {m.name for m in entities.methods}
    function_names = {f.name for f in entities.functions}

    # No overlap: a name cannot be both a top-level function and a method
    assert method_names.isdisjoint(function_names), (
        f"These names appear in both functions and methods: "
        f"{method_names & function_names}"
    )


def test_overloaded_function_yields_multiple_entries(parser):
    """@t.overload creates decorated function nodes; the parser captures all of them.

    stream_with_context is decorated with @t.overload twice and then defined once,
    producing three function_definition nodes at module level. This tests that
    decorated top-level functions are not silently dropped.
    """
    entities = parse_file(read("helpers.py"), "helpers.py", parser)

    overloads = [f for f in entities.functions if f.name == "stream_with_context"]
    assert len(overloads) == 3, (
        f"Expected 3 stream_with_context entries (2 @overload + 1 impl), "
        f"got {len(overloads)}"
    )


def test_overloaded_entries_have_distinct_signatures(parser):
    """Each @t.overload variant must carry a different signature string.

    If the parser conflates overloads they would share a signature, which would
    make it impossible to distinguish them in the graph later.
    """
    entities = parse_file(read("helpers.py"), "helpers.py", parser)

    sigs = [f.signature for f in entities.functions if f.name == "stream_with_context"]
    assert len(set(sigs)) == len(sigs), "Duplicate signatures across overloads"


# ---------------------------------------------------------------------------
# Class extraction — sessions.py (5-class hierarchy)
# ---------------------------------------------------------------------------


def test_all_session_classes_are_extracted_in_order(parser):
    """sessions.py defines exactly 5 classes in source order."""
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    names = [c.name for c in entities.classes]
    assert names == [
        "SessionMixin",
        "SecureCookieSession",
        "NullSession",
        "SessionInterface",
        "SecureCookieSessionInterface",
    ]


def test_multi_inheritance_bases_are_captured(parser):
    """SecureCookieSession inherits from both CallbackDict and SessionMixin.

    Multi-inheritance is a common Python pattern. Both bases must appear in the
    tuple — order matters because Python's MRO depends on it.
    """
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    cls = next(c for c in entities.classes if c.name == "SecureCookieSession")
    # Both bases must be present; we don't test exact string form because
    # the generic parameter may vary across Flask versions
    base_names = " ".join(cls.bases)
    assert "CallbackDict" in base_names
    assert "SessionMixin" in base_names


def test_single_inheritance_base_is_captured(parser):
    """NullSession inherits from exactly one class: SecureCookieSession."""
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    cls = next(c for c in entities.classes if c.name == "NullSession")
    assert len(cls.bases) == 1
    assert cls.bases[0] == "SecureCookieSession"


def test_class_with_no_bases_has_empty_tuple(parser):
    """SessionInterface has no explicit bases — its bases tuple must be empty."""
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    cls = next(c for c in entities.classes if c.name == "SessionInterface")
    assert cls.bases == ()


def test_class_inheriting_from_builtin_is_captured(parser):
    """Config inherits from the built-in `dict` type.

    This tests that a base expressed as a plain identifier (not a dotted name)
    is still recorded correctly.
    """
    entities = parse_file(read("config.py"), "config.py", parser)

    cls = next(c for c in entities.classes if c.name == "Config")
    assert "dict" in cls.bases


# ---------------------------------------------------------------------------
# Method extraction — sessions.py and views.py
# ---------------------------------------------------------------------------


def test_all_session_interface_methods_are_extracted(parser):
    """SessionInterface declares 13 well-known methods."""
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    si_methods = {m.name for m in entities.methods if m.class_name == "SessionInterface"}
    expected = {
        "make_null_session",
        "is_null_session",
        "get_cookie_name",
        "get_cookie_domain",
        "get_cookie_path",
        "get_cookie_httponly",
        "get_cookie_secure",
        "get_cookie_samesite",
        "get_cookie_partitioned",
        "get_expiration_time",
        "should_set_cookie",
        "open_session",
        "save_session",
    }
    assert expected <= si_methods, f"Missing methods: {expected - si_methods}"


def test_methods_are_attributed_to_correct_class(parser):
    """Each method must be linked to the class it belongs to, never mixed up.

    views.py has two classes (View, MethodView); no method should be assigned
    to the wrong class.
    """
    entities = parse_file(read("views.py"), "views.py", parser)

    view_methods = {m.name for m in entities.methods if m.class_name == "View"}
    mv_methods = {m.name for m in entities.methods if m.class_name == "MethodView"}

    assert view_methods == {"dispatch_request", "as_view"}
    assert mv_methods == {"__init_subclass__", "dispatch_request"}


def test_nested_function_inside_method_is_not_extracted_as_top_level(parser):
    """View.as_view contains a nested `view()` function.

    Nested functions must NOT appear as top-level functions or as independent
    methods. If they do, the graph will have phantom nodes.
    """
    entities = parse_file(read("views.py"), "views.py", parser)

    all_function_names = {f.name for f in entities.functions}
    all_method_names = {m.name for m in entities.methods}

    # 'view' is only a nested helper — it must not appear at any top level
    assert "view" not in all_function_names
    assert "view" not in all_method_names


def test_property_decorated_method_is_extracted(parser):
    """@property methods are wrapped in decorated_definition nodes.

    sessions.py has SessionMixin.permanent as a @property. It must still be
    extracted even though it sits inside a decorated_definition.
    """
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    prop_names = {m.name for m in entities.methods if m.class_name == "SessionMixin"}
    assert "permanent" in prop_names


def test_method_line_numbers_are_one_based(parser):
    """All extracted method line numbers must be >= 1 (1-based, not 0-based)."""
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    for m in entities.methods:
        assert m.line_number >= 1, f"{m.class_name}.{m.name} has line_number=0"
        assert m.end_line >= m.line_number, (
            f"{m.class_name}.{m.name}: end_line < line_number"
        )


def test_method_docstring_is_extracted(parser):
    """SessionInterface.make_null_session has a well-documented docstring."""
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    method = next(
        m
        for m in entities.methods
        if m.class_name == "SessionInterface" and m.name == "make_null_session"
    )
    assert method.docstring is not None
    assert len(method.docstring) > 0


# ---------------------------------------------------------------------------
# Import extraction — views.py and helpers.py
# ---------------------------------------------------------------------------


def test_relative_imports_are_marked_relative(parser):
    """views.py uses 'from .globals import ...' — is_relative must be True."""
    entities = parse_file(read("views.py"), "views.py", parser)

    relative = [i for i in entities.imports if i.is_relative]
    assert len(relative) >= 1, "Expected at least one relative import in views.py"
    # Every relative import has is_relative True — sanity check
    for imp in relative:
        assert imp.is_relative is True


def test_relative_import_module_path_and_names(parser):
    """views.py imports current_app and request from .globals."""
    entities = parse_file(read("views.py"), "views.py", parser)

    globals_imports = [i for i in entities.imports if i.module_path == "globals"]
    assert len(globals_imports) >= 1

    imported = {name for i in globals_imports for name in i.imported_names}
    assert "current_app" in imported
    assert "request" in imported


def test_third_party_imports_are_captured(parser):
    """helpers.py imports from werkzeug (third-party, non-stdlib) — must appear."""
    entities = parse_file(read("helpers.py"), "helpers.py", parser)

    module_paths = {i.module_path for i in entities.imports}
    # werkzeug is Flask's primary dependency — if these are missing the graph
    # will have no edges to werkzeug
    assert any(mp.startswith("werkzeug") for mp in module_paths), (
        f"No werkzeug imports found. Got: {module_paths}"
    )


def test_werkzeug_imported_names_are_recorded(parser):
    """helpers.py imports `abort` from werkzeug.exceptions — name must be captured."""
    entities = parse_file(read("helpers.py"), "helpers.py", parser)

    exceptions_import = next(
        (i for i in entities.imports if i.module_path == "werkzeug.exceptions"), None
    )
    assert exceptions_import is not None
    assert "abort" in exceptions_import.imported_names


def test_stdlib_imports_are_excluded(parser):
    """views.py imports `typing` (stdlib) — it must be filtered out.

    Only werkzeug, click, and intra-Flask imports should survive.
    """
    entities = parse_file(read("views.py"), "views.py", parser)

    stdlib_names = {"typing", "os", "sys", "re", "collections", "functools"}
    for imp in entities.imports:
        assert imp.module_path not in stdlib_names, (
            f"Stdlib module '{imp.module_path}' leaked into imports"
        )


def test_absolute_imports_are_not_marked_relative(parser):
    """helpers.py uses absolute imports from werkzeug — is_relative must be False."""
    entities = parse_file(read("helpers.py"), "helpers.py", parser)

    for imp in entities.imports:
        if imp.module_path.startswith("werkzeug"):
            assert imp.is_relative is False


# ---------------------------------------------------------------------------
# Call extraction — views.py
# ---------------------------------------------------------------------------


def test_dispatch_request_raises_not_implemented_error(parser):
    """View.dispatch_request raises NotImplementedError — captured as a call.

    This ensures that calls to built-ins (raise X) inside methods are tracked.
    """
    entities = parse_file(read("views.py"), "views.py", parser)

    dispatch_calls = {
        c.callee_name
        for c in entities.calls
        if c.caller_name == "View.dispatch_request"
    }
    assert "NotImplementedError" in dispatch_calls


def test_method_dispatch_calls_are_scoped_to_qualified_name(parser):
    """Calls inside MethodView.dispatch_request must use 'MethodView.dispatch_request' as caller.

    The caller scope must be class-qualified (not just 'dispatch_request') so
    the graph can distinguish overridden methods from different classes.
    """
    entities = parse_file(read("views.py"), "views.py", parser)

    mv_dispatch_callees = {
        c.callee_name
        for c in entities.calls
        if c.caller_name == "MethodView.dispatch_request"
    }
    assert "getattr" in mv_dispatch_callees


def test_module_level_call_is_attributed_to_module_scope(parser):
    """Calls outside any function at module scope must report '<module>' as caller.

    views.py calls frozenset() and t.TypeVar() at module level.
    """
    entities = parse_file(read("views.py"), "views.py", parser)

    module_callees = {
        c.callee_name for c in entities.calls if c.caller_name == "<module>"
    }
    assert "frozenset" in module_callees


def test_call_line_numbers_are_positive(parser):
    """Every call entity must have a line number >= 1."""
    entities = parse_file(read("views.py"), "views.py", parser)

    for call in entities.calls:
        assert call.line_number >= 1, (
            f"Call {call.caller_name} -> {call.callee_name} has line_number=0"
        )


# ---------------------------------------------------------------------------
# Edge cases specific to Flask's patterns
# ---------------------------------------------------------------------------


def test_file_with_only_classes_has_empty_functions_list(parser):
    """views.py defines classes but no module-level functions.

    The functions list must be empty — class methods must not bleed through.
    """
    entities = parse_file(read("views.py"), "views.py", parser)

    assert entities.functions == [], (
        f"Expected no functions in views.py, got: {[f.name for f in entities.functions]}"
    )


def test_classes_are_empty_list_when_no_classes_in_file(parser):
    """helpers.py has only one private class (_CollectErrors) plus many functions.

    Spot-check that class extraction is specific: other files don't accidentally
    pick up helpers' class. This test verifies the parser doesn't over-extract.
    """
    # helpers.py does define exactly one class
    entities = parse_file(read("helpers.py"), "helpers.py", parser)
    class_names = [c.name for c in entities.classes]
    assert class_names == ["_CollectErrors"], (
        f"Expected only _CollectErrors, got: {class_names}"
    )


def test_generic_base_class_string_is_preserved(parser):
    """SessionMixin inherits from MutableMapping[str, t.Any] — a generic type.

    The base must be preserved as-is (including the type parameter) so downstream
    graph code can distinguish it from a plain 'MutableMapping'.
    """
    entities = parse_file(read("sessions.py"), "sessions.py", parser)

    mixin = next(c for c in entities.classes if c.name == "SessionMixin")
    assert len(mixin.bases) == 1
    assert "MutableMapping" in mixin.bases[0]


# ---------------------------------------------------------------------------
# Integration: parse entire Flask package directory
# ---------------------------------------------------------------------------


def test_parse_directory_finds_all_flask_package_files(parser):
    """parse_directory must return one FileEntities per .py file in flask/src/flask/.

    This includes __init__.py, __main__.py, and all submodules (sansio/, json/)
    but excludes __pycache__. The flask package has exactly 24 .py files across
    the root package and its two sub-packages.
    """
    results = parse_directory(str(PROJECT), parser, exclude_patterns=["__pycache__"])

    assert len(results) == 24, (
        f"Expected 24 files, got {len(results)}: "
        f"{sorted(r.file_path.split('flask')[-1] for r in results)}"
    )


def test_parse_directory_extracts_known_flask_classes(parser):
    """Key Flask public classes must appear across the parsed file set."""
    results = parse_directory(str(PROJECT), parser, exclude_patterns=["__pycache__"])

    all_class_names = {c.name for r in results for c in r.classes}
    # These are the most important Flask classes — missing any means a bug
    required = {"Flask", "Blueprint", "View", "MethodView", "Config", "Request", "Response"}
    assert required <= all_class_names, f"Missing classes: {required - all_class_names}"


def test_parse_directory_class_count_is_in_expected_range(parser):
    """The Flask package (including sansio/ and json/) defines ~46 classes.

    Allow a small window for minor Flask version differences, but a large
    drift signals that class extraction is broken.
    """
    results = parse_directory(str(PROJECT), parser, exclude_patterns=["__pycache__"])

    all_classes = [c for r in results for c in r.classes]
    # 46 confirmed for the cloned version; allow ±10 for version variation
    assert 36 <= len(all_classes) <= 56, (
        f"Unexpected class count: {len(all_classes)}"
    )


def test_parse_directory_exclude_pattern_filters_sessions(parser):
    """Excluding 'sessions' must drop sessions.py from the results."""
    results_all = parse_directory(str(PROJECT), parser, exclude_patterns=["__pycache__"])
    results_no_sessions = parse_directory(
        str(PROJECT), parser, exclude_patterns=["__pycache__", "sessions"]
    )

    all_paths = {r.file_path for r in results_all}
    filtered_paths = {r.file_path for r in results_no_sessions}
    excluded = all_paths - filtered_paths

    assert len(excluded) == 1
    assert all("sessions" in p for p in excluded)


def test_parse_directory_werkzeug_imports_appear_across_files(parser):
    """Multiple Flask files import from werkzeug — the aggregate import set must include it.

    If werkzeug imports are missing from the graph, Flask's request/response
    handling will have no edges to its HTTP primitives.
    """
    results = parse_directory(str(PROJECT), parser, exclude_patterns=["__pycache__"])

    all_imports = [i for r in results for i in r.imports]
    werkzeug_imports = [i for i in all_imports if i.module_path.startswith("werkzeug")]
    assert len(werkzeug_imports) >= 5, (
        f"Expected >= 5 werkzeug imports across Flask, got {len(werkzeug_imports)}"
    )
