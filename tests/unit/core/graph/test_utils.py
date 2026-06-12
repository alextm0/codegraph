from codegraph.core.graph.utils import normalize_path
from codegraph.core.graph.queries.subgraph import expand_qnames_with_file_nodes


class TestNormalizePath:
    def test_forward_slashes_unchanged(self):
        assert normalize_path("src/auth/login.py") == "src/auth/login.py"

    def test_backslashes_replaced(self):
        assert normalize_path("src\\auth\\login.py") == "src/auth/login.py"

    def test_mixed_slashes(self):
        assert normalize_path("src\\auth/login.py") == "src/auth/login.py"

    def test_empty_string(self):
        assert normalize_path("") == ""

    def test_single_backslash(self):
        assert normalize_path("file\\name.py") == "file/name.py"

    def test_unc_style_path(self):
        result = normalize_path("\\\\server\\share\\file.py")
        assert result == "//server/share/file.py"

    def test_already_normalized_unchanged(self):
        p = "a/b/c/d.py"
        assert normalize_path(p) == p


class TestExpandQNames:
    def test_expand_qnames_adds_file_node_for_entities(self) -> None:
        qnames = [
            "src/pkg/tools.py::get_context",
            "src/pkg/tools.py::query_deps",
        ]
        expanded = expand_qnames_with_file_nodes(qnames)
        assert "src/pkg/tools.py::get_context" in expanded
        assert "src/pkg/tools.py" in expanded

    def test_expand_qnames_uses_explicit_file_paths(self) -> None:
        expanded = expand_qnames_with_file_nodes(
            ["other.py::fn"],
            file_paths=["src/pkg/tools.py"],
        )
        assert "src/pkg/tools.py" in expanded
