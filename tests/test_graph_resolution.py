"""Unit tests for graph_builder resolution helpers — no Neo4j required."""

import pytest

from src.parser.models import (
    FileEntities,
    FunctionEntity,
    ClassEntity,
    MethodEntity,
    ImportEntity,
    CallEntity,
)
from src.graph.graph_builder import (
    _build_entity_lookup,
    _build_import_map,
    _resolve_caller,
    _resolve_callee,
    _resolve_base_class,
    _resolve_import_to_file_path,
)


# ---------------------------------------------------------------------------
# _resolve_import_to_file_path
# ---------------------------------------------------------------------------

class TestResolveImportToFilePath:
    """Tests for dotted module path -> file path resolution."""

    ALL_PATHS = [
        "user_auth/models/user.py",
        "user_auth/models/base.py",
        "user_auth/services/auth_service.py",
        "user_auth/utils/validators.py",
        "user_auth/utils/admin_user.py",
        "helpers.py",
    ]

    def test_resolves_dotted_module(self):
        result = _resolve_import_to_file_path("user_auth.models.user", self.ALL_PATHS)
        assert result == "user_auth/models/user.py"

    def test_resolves_with_stripped_prefix(self):
        result = _resolve_import_to_file_path("user_auth.utils.validators", self.ALL_PATHS)
        assert result == "user_auth/utils/validators.py"

    def test_no_false_suffix_match(self):
        """'user.py' must NOT match 'admin_user.py'."""
        result = _resolve_import_to_file_path("user_auth.models.user", [
            "user_auth/utils/admin_user.py",
            "user_auth/models/user.py",
        ])
        assert result == "user_auth/models/user.py"

    def test_no_false_suffix_match_single_segment(self):
        """Single-segment suffix 'user.py' must not match 'admin_user.py'."""
        result = _resolve_import_to_file_path("project.user", [
            "project/admin_user.py",
        ])
        assert result is None

    def test_single_segment_module(self):
        result = _resolve_import_to_file_path("helpers", self.ALL_PATHS)
        assert result == "helpers.py"

    def test_empty_module_path_returns_none(self):
        assert _resolve_import_to_file_path("", self.ALL_PATHS) is None

    def test_unresolvable_module_returns_none(self):
        assert _resolve_import_to_file_path("nonexistent.module", self.ALL_PATHS) is None

    def test_relative_dots_are_stripped(self):
        result = _resolve_import_to_file_path("..models.user", self.ALL_PATHS)
        assert result == "user_auth/models/user.py"


# ---------------------------------------------------------------------------
# _build_entity_lookup
# ---------------------------------------------------------------------------

def _make_fe(file_path: str, functions: list[str] = (), classes: list[str] = (),
             methods: list[tuple[str, str]] = ()) -> FileEntities:
    """Helper to build a FileEntities with minimal fields."""
    fe = FileEntities(file_path=file_path)
    for name in functions:
        fe.functions.append(FunctionEntity(name=name, file_path=file_path,
                                           line_number=1, end_line=5, signature=f"def {name}()"))
    for name in classes:
        fe.classes.append(ClassEntity(name=name, file_path=file_path,
                                      line_number=1, end_line=10))
    for cls_name, meth_name in methods:
        fe.methods.append(MethodEntity(name=meth_name, class_name=cls_name,
                                       file_path=file_path, line_number=1,
                                       end_line=5, signature=f"def {meth_name}(self)"))
    return fe


class TestBuildEntityLookup:
    """Tests for _build_entity_lookup."""

    def test_maps_function_name_to_qualified(self):
        fe = _make_fe("src/utils.py", functions=["validate"])
        lookup = _build_entity_lookup([fe])
        assert lookup["validate"] == ["src/utils.py::validate"]

    def test_maps_class_name_to_qualified(self):
        fe = _make_fe("models/user.py", classes=["User"])
        lookup = _build_entity_lookup([fe])
        assert lookup["User"] == ["models/user.py::User"]

    def test_maps_method_dotted_and_bare(self):
        fe = _make_fe("services/auth.py", methods=[("AuthService", "login")])
        lookup = _build_entity_lookup([fe])
        assert "AuthService.login" in lookup
        assert "login" in lookup

    def test_duplicate_function_names_keep_all_candidates(self):
        fe1 = _make_fe("a.py", functions=["validate"])
        fe2 = _make_fe("b.py", functions=["validate"])
        lookup = _build_entity_lookup([fe1, fe2])
        assert len(lookup["validate"]) == 2
        assert "a.py::validate" in lookup["validate"]
        assert "b.py::validate" in lookup["validate"]

    def test_empty_entities_returns_empty_lookup(self):
        lookup = _build_entity_lookup([])
        assert lookup == {}


# ---------------------------------------------------------------------------
# _build_import_map
# ---------------------------------------------------------------------------

class TestBuildImportMap:
    """Tests for _build_import_map."""

    ALL_PATHS = [
        "src/models/user.py",
        "src/utils/crypto.py",
    ]

    def test_from_import_maps_names_to_file(self):
        fe = FileEntities(
            file_path="src/services/auth.py",
            imports=[ImportEntity(module_path="src.utils.crypto",
                                  imported_names=("hash_password", "verify_hash"))],
        )
        import_map = _build_import_map(fe, self.ALL_PATHS)
        assert import_map["hash_password"] == "src/utils/crypto.py"
        assert import_map["verify_hash"] == "src/utils/crypto.py"

    def test_bare_import_maps_last_segment(self):
        fe = FileEntities(
            file_path="src/main.py",
            imports=[ImportEntity(module_path="src.utils.crypto")],
        )
        import_map = _build_import_map(fe, self.ALL_PATHS)
        assert import_map["crypto"] == "src/utils/crypto.py"

    def test_unresolvable_import_skipped(self):
        fe = FileEntities(
            file_path="src/main.py",
            imports=[ImportEntity(module_path="nonexistent.module",
                                  imported_names=("foo",))],
        )
        import_map = _build_import_map(fe, self.ALL_PATHS)
        assert import_map == {}

    def test_no_imports_returns_empty(self):
        fe = FileEntities(file_path="src/main.py")
        import_map = _build_import_map(fe, self.ALL_PATHS)
        assert import_map == {}


# ---------------------------------------------------------------------------
# _resolve_caller
# ---------------------------------------------------------------------------

class TestResolveCaller:
    """Tests for _resolve_caller."""

    def test_module_scope_returns_file_path(self):
        assert _resolve_caller("<module>", "src/main.py") == "src/main.py"

    def test_top_level_function(self):
        assert _resolve_caller("validate", "src/utils.py") == "src/utils.py::validate"

    def test_dotted_method_name(self):
        result = _resolve_caller("AuthService.login", "src/auth.py")
        assert result == "src/auth.py::AuthService.login"

    def test_normalizes_windows_paths(self):
        result = _resolve_caller("main", "src\\main.py")
        assert result == "src/main.py::main"


# ---------------------------------------------------------------------------
# _resolve_callee
# ---------------------------------------------------------------------------

class TestResolveCallee:
    """Tests for _resolve_callee with import-aware resolution."""

    def test_import_match_takes_priority(self):
        lookup = {"validate": ["a.py::validate", "b.py::validate"]}
        import_map = {"validate": "b.py"}
        result = _resolve_callee("validate", lookup, "c.py", import_map)
        assert result == "b.py::validate"

    def test_same_file_match_when_no_import(self):
        lookup = {"validate": ["a.py::validate", "b.py::validate"]}
        import_map = {}
        result = _resolve_callee("validate", lookup, "a.py", import_map)
        assert result == "a.py::validate"

    def test_unique_global_match_when_no_import_or_local(self):
        lookup = {"validate": ["other.py::validate"]}
        import_map = {}
        result = _resolve_callee("validate", lookup, "main.py", import_map)
        assert result == "other.py::validate"

    def test_ambiguous_returns_none(self):
        lookup = {"validate": ["a.py::validate", "b.py::validate"]}
        import_map = {}
        result = _resolve_callee("validate", lookup, "c.py", import_map)
        assert result is None

    def test_unknown_callee_returns_none(self):
        result = _resolve_callee("nonexistent", {}, "main.py", {})
        assert result is None


# ---------------------------------------------------------------------------
# _resolve_base_class
# ---------------------------------------------------------------------------

class TestResolveBaseClass:
    """Tests for _resolve_base_class with import-aware resolution."""

    def test_import_match_takes_priority(self):
        lookup = {"BaseModel": ["a.py::BaseModel", "b.py::BaseModel"]}
        import_map = {"BaseModel": "a.py"}
        result = _resolve_base_class("BaseModel", lookup, "c.py", import_map)
        assert result == "a.py::BaseModel"

    def test_same_file_match_when_no_import(self):
        lookup = {"Base": ["models/base.py::Base", "other/base.py::Base"]}
        import_map = {}
        result = _resolve_base_class("Base", lookup, "models/base.py", import_map)
        assert result == "models/base.py::Base"

    def test_unique_global_match(self):
        lookup = {"BaseModel": ["models/base.py::BaseModel"]}
        result = _resolve_base_class("BaseModel", lookup, "services/auth.py", {})
        assert result == "models/base.py::BaseModel"

    def test_ambiguous_returns_none(self):
        lookup = {"Base": ["a.py::Base", "b.py::Base"]}
        result = _resolve_base_class("Base", lookup, "c.py", {})
        assert result is None

    def test_unknown_base_returns_none(self):
        result = _resolve_base_class("Unknown", {}, "main.py", {})
        assert result is None
