from pathlib import Path
import pytest
from codegraph.utils.ignore import is_ignored, load_ignore_patterns

def test_load_ignore_patterns_nonexistent():
    patterns = load_ignore_patterns("nonexistent_file")
    assert patterns == []

def test_load_ignore_patterns_valid(tmp_path):
    ignore_file = tmp_path / ".cgignore"
    ignore_file.write_text("website/\n# comment\n\n*.pyc\n", encoding="utf-8")
    
    patterns = load_ignore_patterns(ignore_file)
    assert patterns == ["website/", "*.pyc"]

def test_is_ignored_substring():
    patterns = ["temp", "build"]
    assert is_ignored("src/temp_utils.py", patterns) is True
    assert is_ignored("build/app.js", patterns) is True
    assert is_ignored("src/main.py", patterns) is False

def test_is_ignored_glob():
    patterns = ["*.pyc", "tests/fixtures/*"]
    assert is_ignored("main.pyc", patterns) is True
    assert is_ignored("tests/fixtures/data.json", patterns) is True
    assert is_ignored("tests/parser/test_p.py", patterns) is False

def test_is_ignored_directory():
    patterns = ["venv/", "node_modules/"]
    assert is_ignored("venv/bin/python", patterns) is True
    assert is_ignored("src/node_modules/lodash/index.js", patterns) is True
    assert is_ignored("venve/main.py", patterns) is False

def test_is_ignored_case_and_separator():
    patterns = ["TEMP/"]
    assert is_ignored("temp/file.txt", patterns) is True
    assert is_ignored("TEMP\\file.txt", patterns) is True
