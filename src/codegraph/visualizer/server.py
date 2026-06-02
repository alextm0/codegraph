"""Backward-compatible entry point for the visualizer FastAPI app."""

from codegraph.visualizer.app import create_app

__all__ = ["create_app"]
