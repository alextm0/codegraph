"""Tests for the Python tree-sitter parser against the 'user_auth' fixture.

Convention: one test file per fixture project.
  tests/fixtures/user_auth/  <->  tests/test_parser_user_auth.py  (this file)
  tests/fixtures/<name>/     <->  tests/test_parser_<name>.py     (future projects)

Each test file defines its own PROJECT constant and read() helper so tests
are fully self-contained. To add a new fixture project:
  1. Create tests/fixtures/<name>/ with the Python code to parse.
  2. Create tests/test_parser_<name>.py with PROJECT and read() pointing to it.

Fixture layout (tests/fixtures/user_auth/):
  models/user.py           — BaseModel + User classes, create_guest_user()
  utils/validators.py      — 4 top-level functions, stdlib-only imports
  services/auth_service.py — AuthService class, cross-module imports and calls
  models/__init__.py       — single relative import
"""

from pathlib import Path

import pytest

from codegraph.core.parser.models import FileEntities
from codegraph.core.parser.python_parser import create_parser, parse_directory, parse_file

# Reorganized path: tests/unit/core/parser/test_user_auth.py
# Fixtures are at: tests/fixtures/
FIXTURES_DIR = Path(__file__).parents[3] / "fixtures"

PROJECT = FIXTURES_DIR / "user_auth"


@pytest.fixture(scope="module")
def parser():
    return create_parser()


def read(relative_path: str) -> bytes:
    """Read a file from the project fixture."""
    return (PROJECT / relative_path).read_bytes()


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------

def test_extracts_all_top_level_functions(parser):
    """validators.py defines exactly 4 top-level functions."""
    entities = parse_file(read("utils/validators.py"), "validators.py", parser)

    names = [f.name for f in entities.functions]
    assert names == ["validate_email", "validate_username", "validate_password", "validate_password_strength"]


def test_function_has_correct_line_span(parser):
    """validate_email starts on line 9 and ends after its body."""
    entities = parse_file(read("utils/validators.py"), "validators.py", parser)

    fn = next(f for f in entities.functions if f.name == "validate_email")
    assert fn.line_number == 9
    assert fn.end_line > fn.line_number


def test_function_signature_contains_parameter_name(parser):
    """The signature of validate_email should include the 'email' parameter."""
    entities = parse_file(read("utils/validators.py"), "validators.py", parser)

    fn = next(f for f in entities.functions if f.name == "validate_email")
    assert "email" in fn.signature


def test_function_docstring_is_extracted(parser):
    """validate_email has a docstring that describes its purpose."""
    entities = parse_file(read("utils/validators.py"), "validators.py", parser)

    fn = next(f for f in entities.functions if f.name == "validate_email")
    assert fn.docstring is not None
    assert "email" in fn.docstring.lower()


def test_top_level_functions_exclude_methods(parser):
    """user.py has no top-level functions except create_guest_user — class methods must not appear here."""
    entities = parse_file(read("models/user.py"), "user.py", parser)

    names = [f.name for f in entities.functions]
    assert names == ["create_guest_user"]


# ---------------------------------------------------------------------------
# Class extraction
# ---------------------------------------------------------------------------

def test_extracts_all_classes(parser):
    """user.py defines exactly BaseModel and User — in that order."""
    entities = parse_file(read("models/user.py"), "user.py", parser)

    names = [c.name for c in entities.classes]
    assert names == ["BaseModel", "User"]


def test_class_inheritance_captured(parser):
    """User inherits from BaseModel — the bases tuple must reflect that."""
    entities = parse_file(read("models/user.py"), "user.py", parser)

    user = next(c for c in entities.classes if c.name == "User")
    assert user.bases == ("BaseModel",)


def test_base_class_has_no_bases(parser):
    """BaseModel has no parent classes."""
    entities = parse_file(read("models/user.py"), "user.py", parser)

    base = next(c for c in entities.classes if c.name == "BaseModel")
    assert base.bases == ()


# ---------------------------------------------------------------------------
# Method extraction
# ---------------------------------------------------------------------------

def test_extracts_all_methods_with_correct_class_assignment(parser):
    """Every method must be linked to the class it belongs to, not mixed up."""
    entities = parse_file(read("models/user.py"), "user.py", parser)

    base_methods = {m.name for m in entities.methods if m.class_name == "BaseModel"}
    user_methods = {m.name for m in entities.methods if m.class_name == "User"}

    assert base_methods == {"__init__", "to_dict", "validate_id"}
    assert user_methods == {"__init__", "to_dict", "display_name"}


def test_decorated_method_is_included(parser):
    """@staticmethod validate_id on BaseModel must still be extracted."""
    entities = parse_file(read("models/user.py"), "user.py", parser)

    names = [(m.class_name, m.name) for m in entities.methods]
    assert ("BaseModel", "validate_id") in names


def test_method_docstring_is_extracted(parser):
    """BaseModel.__init__ has a one-line docstring."""
    entities = parse_file(read("models/user.py"), "user.py", parser)

    init = next(m for m in entities.methods if m.class_name == "BaseModel" and m.name == "__init__")
    assert init.docstring is not None
    assert len(init.docstring) > 0


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------

def test_absolute_imports_extracted_with_correct_module_paths(parser):
    """auth_service.py has two absolute imports from the project package."""
    entities = parse_file(read("services/auth_service.py"), "auth_service.py", parser)

    module_paths = {i.module_path for i in entities.imports}
    assert module_paths == {"user_auth.models.user", "user_auth.utils.validators"}


def test_imported_names_captured_for_each_module(parser):
    """Each import statement lists the names it pulls in."""
    entities = parse_file(read("services/auth_service.py"), "auth_service.py", parser)

    by_module = {i.module_path: i.imported_names for i in entities.imports}

    assert "User" in by_module["user_auth.models.user"]
    assert "validate_email" in by_module["user_auth.utils.validators"]
    assert "validate_username" in by_module["user_auth.utils.validators"]
    assert "validate_password" in by_module["user_auth.utils.validators"]


def test_absolute_import_is_not_marked_relative(parser):
    """Absolute imports must have is_relative=False."""
    entities = parse_file(read("services/auth_service.py"), "auth_service.py", parser)

    for imp in entities.imports:
        assert imp.is_relative is False


def test_relative_import_is_marked_relative(parser):
    """models/__init__.py uses 'from .user import User' — a relative import."""
    entities = parse_file(read("models/__init__.py"), "models/__init__.py", parser)

    assert len(entities.imports) == 1
    imp = entities.imports[0]
    assert imp.is_relative is True
    assert "User" in imp.imported_names


def test_stdlib_imports_are_excluded(parser):
    """validators.py imports 're' and 'logging' — both stdlib, both must be filtered out."""
    entities = parse_file(read("utils/validators.py"), "validators.py", parser)

    assert entities.imports == []


# ---------------------------------------------------------------------------
# Call extraction
# ---------------------------------------------------------------------------

def test_intra_file_call_is_captured(parser):
    """validate_password calls validate_password_strength within the same file."""
    entities = parse_file(read("utils/validators.py"), "validators.py", parser)

    call = next(
        c for c in entities.calls
        if c.callee_name == "validate_password_strength" and c.caller_name == "validate_password"
    )
    assert call.line_number >= 1


def test_caller_scope_is_method_qualified(parser):
    """Calls inside AuthService.register must have caller_name == 'AuthService.register'."""
    entities = parse_file(read("services/auth_service.py"), "auth_service.py", parser)

    register_callees = {
        c.callee_name for c in entities.calls if c.caller_name == "AuthService.register"
    }
    assert "validate_username" in register_callees
    assert "validate_email" in register_callees
    assert "validate_password" in register_callees


def test_module_level_call_has_module_scope(parser):
    """A call at module scope (outside any function) reports '<module>' as caller."""
    # create_guest_user() is called at module scope — but in our fixture it's just
    # defined, not called at module level. Use inline source for this edge case.
    source = b"result = len([1, 2, 3])\n"
    entities = parse_file(source, "inline.py", parser)

    module_calls = [c for c in entities.calls if c.caller_name == "<module>"]
    assert any(c.callee_name == "len" for c in module_calls)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_file_returns_all_empty_lists(parser):
    """An empty source file must parse without error and return empty entity lists."""
    entities = parse_file(b"", "empty.py", parser)

    assert isinstance(entities, FileEntities)
    assert entities.functions == []
    assert entities.classes == []
    assert entities.methods == []
    assert entities.imports == []
    assert entities.calls == []


def test_file_path_is_stored_on_entities(parser):
    """The file_path passed to parse_file must be accessible on the returned object."""
    entities = parse_file(b"x = 1\n", "some/path.py", parser)

    assert entities.file_path == "some/path.py"


def test_syntax_error_file_does_not_raise(parser):
    """tree-sitter is error-tolerant: a broken file must not raise and must return a FileEntities."""
    broken = b"def foo(\n    x: int\n# missing closing paren\nclass Bar:\n    pass\n"
    entities = parse_file(broken, "broken.py", parser)

    assert isinstance(entities, FileEntities)


# ---------------------------------------------------------------------------
# Integration: parse entire fixture directory
# ---------------------------------------------------------------------------

def test_parse_directory_finds_all_fixture_files(parser):
    """parse_directory must return one FileEntities per .py file in the fixture tree."""
    results = parse_directory(str(PROJECT), parser)

    # The fixture tree has exactly 7 .py files
    assert len(results) == 7


def test_parse_directory_aggregates_entities_across_files(parser):
    """Entities from all files are collected — spot-check key names from each module."""
    results = parse_directory(str(PROJECT), parser)

    all_functions = [f for r in results for f in r.functions]
    all_classes = [c for r in results for c in r.classes]
    all_methods = [m for r in results for m in r.methods]

    assert {f.name for f in all_functions} >= {"validate_email", "validate_username", "create_guest_user"}
    assert {c.name for c in all_classes} >= {"BaseModel", "User", "AuthService"}
    assert len(all_methods) == 9  # 3 on BaseModel + 3 on User + 3 on AuthService


def test_parse_directory_exclude_pattern_filters_files(parser):
    """Files whose path contains an excluded pattern must be skipped."""
    results_all = parse_directory(str(PROJECT), parser)
    results_no_services = parse_directory(str(PROJECT), parser, exclude_patterns=["services"])

    all_paths = {r.file_path for r in results_all}
    filtered_paths = {r.file_path for r in results_no_services}

    excluded = all_paths - filtered_paths
    assert all("services" in p for p in excluded)
    assert len(excluded) >= 1
