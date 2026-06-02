import os
from codegraph.utils.paths import make_relative_path, make_relative_qualified_name


class TestMakeRelativePath:
    def test_basic_relative(self, tmp_path):
        child = str(tmp_path / "src" / "auth.py")
        result = make_relative_path(child, str(tmp_path))
        assert result == "src/auth.py"

    def test_already_relative_style(self, tmp_path):
        child = str(tmp_path / "a" / "b" / "c.py")
        result = make_relative_path(child, str(tmp_path))
        assert result == "a/b/c.py"

    def test_same_file_as_root(self, tmp_path):
        result = make_relative_path(str(tmp_path), str(tmp_path))
        assert result == "."

    def test_empty_string_returns_empty(self):
        result = make_relative_path("", "/some/root")
        assert result == ""

    def test_forward_slashes_in_output(self, tmp_path):
        child = str(tmp_path / "sub" / "file.py")
        result = make_relative_path(child, str(tmp_path))
        assert "\\" not in result

    def test_already_relative_path_unchanged(self, tmp_path):
        rel = "src/codegraph/mcp/tools.py"
        result = make_relative_path(rel, str(tmp_path / "projects" / "codegraph"))
        assert result == rel

    def test_relpath_failure_returns_abs_unchanged(self, monkeypatch):
        # When relpath cannot compute a relative path, return the input unchanged.
        def raising_relpath(path, start):
            raise ValueError("cannot relpath")

        monkeypatch.setattr(os.path, "relpath", raising_relpath)
        abs_path = "/mnt/other/foo.py"
        result = make_relative_path(abs_path, "/project")
        assert result == abs_path


class TestMakeRelativeQualifiedName:
    def test_replaces_abs_prefix(self):
        qn = "/abs/path/auth.py::login"
        result = make_relative_qualified_name(qn, "/abs/path/auth.py", "auth.py")
        assert result == "auth.py::login"

    def test_no_match_returns_unchanged(self):
        qn = "/other/path/service.py::register"
        result = make_relative_qualified_name(qn, "/abs/path/auth.py", "auth.py")
        assert result == "/other/path/service.py::register"

    def test_empty_abs_path_returns_unchanged(self):
        qn = "auth.py::login"
        result = make_relative_qualified_name(qn, "", "auth.py")
        assert result == "auth.py::login"

    def test_class_method_suffix_preserved(self):
        qn = "/project/src/auth.py::AuthService.login"
        result = make_relative_qualified_name(qn, "/project/src/auth.py", "src/auth.py")
        assert result == "src/auth.py::AuthService.login"

    def test_partial_prefix_not_replaced(self):
        # qualified_name starts with a different file that shares a prefix
        qn = "/project/src/auth_extra.py::func"
        result = make_relative_qualified_name(qn, "/project/src/auth.py", "src/auth.py")
        assert result == "/project/src/auth_extra.py::func"
