"""Shared utility functions for the graph module."""


def normalize_path(path: str) -> str:
    """Normalize OS path separators to forward slashes for consistent storage."""
    return path.replace("\\", "/")
