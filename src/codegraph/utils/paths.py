"""Shared path utilities for converting absolute paths to project-relative ones."""

import os


def make_relative_path(abs_path: str, project_root: str) -> str:
    """Convert an absolute path to a relative path from project_root."""
    if not abs_path:
        return abs_path
    try:
        return os.path.relpath(abs_path, project_root).replace("\\", "/")
    except ValueError:
        # relpath raises ValueError on Windows when paths are on different drives.
        return abs_path


def make_relative_qualified_name(
    qualified_name: str, abs_file_path: str, rel_file_path: str
) -> str:
    """Replace the absolute file prefix in a qualified_name with the relative path.

    e.g. "/abs/path/auth.py::login" → "auth.py::login"
    Returns qualified_name unchanged if it doesn't start with abs_file_path.
    """
    if abs_file_path and qualified_name.startswith(abs_file_path):
        suffix = qualified_name[len(abs_file_path) :]
        return rel_file_path + suffix
    return qualified_name
