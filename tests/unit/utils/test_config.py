from pathlib import Path
import os
import yaml
import pytest
from codegraph.utils.config import load_raw_config, resolve_project_root

def test_load_raw_config_nonexistent():
    config = load_raw_config("nonexistent.yaml")
    assert config == {}

def test_load_raw_config_empty(tmp_path):
    config_file = tmp_path / "empty.yaml"
    config_file.write_text("", encoding="utf-8")
    config = load_raw_config(config_file)
    assert config == {}

def test_load_raw_config_valid(tmp_path):
    config_data = {"project_root": "src", "parser": {"exclude_patterns": ["test/"]}}
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")
    
    config = load_raw_config(config_file)
    assert config == config_data

def test_resolve_project_root_absolute():
    # Use a dummy absolute path
    abs_path = "C:/Work/Project" if os.name == "nt" else "/work/project"
    config = {"project_root": abs_path}
    config_path = Path("config.yaml")
    
    root = resolve_project_root(config, config_path)
    assert str(root).replace("\\", "/") == abs_path

def test_resolve_project_root_relative(tmp_path):
    config = {"project_root": "src"}
    config_path = tmp_path / "config.yaml"
    # The expected root should be tmp_path / "src"
    root = resolve_project_root(config, config_path)
    assert root == (tmp_path / "src").resolve()

def test_resolve_project_root_default(tmp_path):
    config = {} # No project_root
    config_path = tmp_path / "config.yaml"
    # Default is ".", which resolves to tmp_path
    root = resolve_project_root(config, config_path)
    assert root == tmp_path.resolve()
