import pytest
from tree_sitter import Language

from codegraph.utils.tree_sitter_manager import (
    TreeSitterManager,
    get_tree_sitter_manager,
    LANGUAGE_ALIASES,
    SUPPORTED_EXTENSIONS,
)


class TestTreeSitterManager:
    def test_get_language_python_returns_language(self):
        mgr = TreeSitterManager()
        lang = mgr.get_language("python")
        assert isinstance(lang, Language)

    def test_get_language_alias_py_resolves_to_python(self):
        mgr = TreeSitterManager()
        lang = mgr.get_language("py")
        assert isinstance(lang, Language)

    def test_alias_and_canonical_return_same_object(self):
        mgr = TreeSitterManager()
        lang_py = mgr.get_language("py")
        lang_python = mgr.get_language("python")
        # Both should resolve to the same cached object
        assert lang_py is lang_python

    def test_caching_returns_same_object(self):
        mgr = TreeSitterManager()
        first = mgr.get_language("python")
        second = mgr.get_language("python")
        assert first is second

    def test_unsupported_language_raises_value_error(self):
        mgr = TreeSitterManager()
        with pytest.raises(ValueError, match="Unsupported language"):
            mgr.get_language("javascript")

    def test_get_tree_sitter_manager_singleton(self):
        mgr1 = get_tree_sitter_manager()
        mgr2 = get_tree_sitter_manager()
        assert mgr1 is mgr2

    def test_get_tree_sitter_manager_returns_manager_instance(self):
        mgr = get_tree_sitter_manager()
        assert isinstance(mgr, TreeSitterManager)


class TestConstants:
    def test_supported_extensions_includes_py(self):
        assert ".py" in SUPPORTED_EXTENSIONS
        assert SUPPORTED_EXTENSIONS[".py"] == "python"

    def test_language_aliases_includes_py(self):
        assert "py" in LANGUAGE_ALIASES
        assert LANGUAGE_ALIASES["py"] == "python"
