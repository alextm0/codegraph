from codegraph.core.graph.utils import normalize_path


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
