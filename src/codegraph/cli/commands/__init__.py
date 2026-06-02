"""CLI command helpers package."""

from codegraph.cli.commands._shared import (
    _initialize_db,
    _read_build_timestamp,
    _write_build_timestamp,
)
from codegraph.cli.commands.build import rebuild_helper
from codegraph.cli.commands.doctor import doctor_helper
from codegraph.cli.commands.explain import explain_helper
from codegraph.cli.commands.init import _write_env_password, init_helper
from codegraph.cli.commands.install import (
    _claude_desktop_config_paths,
    _claude_json_has_codegraph,
    _find_mcp_registrations,
    _gemini_settings_has_codegraph,
    _gemini_settings_paths,
    _mcp_json_has_codegraph,
    _write_claude_desktop_json,
    _write_gemini_settings_json,
    _write_project_mcp_json,
    install_helper,
)
from codegraph.cli.commands.query import query_helper
from codegraph.cli.commands.status import stats_helper, status_helper
from codegraph.cli.commands.visualize import visualize_helper
from codegraph.cli.commands.watch import watch_helper

__all__ = [
    "_claude_desktop_config_paths",
    "_claude_json_has_codegraph",
    "_find_mcp_registrations",
    "_gemini_settings_has_codegraph",
    "_gemini_settings_paths",
    "_initialize_db",
    "_mcp_json_has_codegraph",
    "_read_build_timestamp",
    "_write_build_timestamp",
    "_write_claude_desktop_json",
    "_write_env_password",
    "_write_gemini_settings_json",
    "_write_project_mcp_json",
    "doctor_helper",
    "explain_helper",
    "init_helper",
    "install_helper",
    "query_helper",
    "rebuild_helper",
    "stats_helper",
    "status_helper",
    "visualize_helper",
    "watch_helper",
]
