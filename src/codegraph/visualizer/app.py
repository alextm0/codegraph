"""FastAPI application factory for the CodeGraph visualizer."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from neo4j import Driver

from codegraph.visualizer.context import VisualizerContext
from codegraph.visualizer.query_service import update_project_history
from codegraph.visualizer.routes import register_routes

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    driver: Driver,
    raw_config: dict[str, Any],
    project_root: str = "",
    config_path: Path | None = None,
    dev_mode: bool = False,
    watch_mode: bool = False,
) -> FastAPI:
    """Create and return the FastAPI application."""
    base_dir = config_path.parent if config_path else Path.cwd()
    _normalize_project_history(raw_config, config_path, project_root)

    connected_clients: set = set()
    watcher_cleanup: Callable[[], None] | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.event_loop = asyncio.get_running_loop()
        try:
            yield
        finally:
            if watcher_cleanup is not None:
                watcher_cleanup()

    app = FastAPI(
        title="CodeGraph Visualizer",
        description="Interactive graph visualization for CodeGraph retrieval results.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    ctx = VisualizerContext(
        driver=driver,
        raw_config=raw_config,
        project_root=project_root,
        config_path=config_path,
        base_dir=base_dir,
        schedule_broadcast=lambda _msg: None,
    )

    async def broadcast(message: dict) -> None:
        if not connected_clients:
            return
        for client in list(connected_clients):
            try:
                await client.send_json(message)
            except Exception:
                connected_clients.discard(client)

    def schedule_broadcast(message: dict) -> None:
        loop = getattr(app.state, "event_loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast(message), loop)

    ctx.schedule_broadcast = schedule_broadcast

    if watch_mode and project_root:
        watcher_cleanup = _start_file_watcher(
            driver, raw_config, project_root, schedule_broadcast
        )

    register_routes(app, ctx, connected_clients)
    _mount_static(app, dev_mode)

    return app


def _normalize_project_history(
    raw_config: dict[str, Any],
    config_path: Path | None,
    project_root: str,
) -> None:
    """Deduplicate project_history and persist when it changes."""
    if not (config_path and config_path.exists()):
        return

    from codegraph.utils.config import save_raw_config
    from codegraph.utils.paths import resolve_absolute_path

    history = raw_config.get("project_history") or []
    cleaned_history: list[dict[str, Any]] = []
    seen_abs: set[str] = set()
    for item in history:
        abs_p = resolve_absolute_path(item.get("path", ""))
        if abs_p not in seen_abs:
            seen_abs.add(abs_p)
            cleaned_history.append(item)
    raw_config["project_history"] = cleaned_history[:5]

    old_history = list(raw_config.get("project_history") or [])
    update_project_history(raw_config, project_root)
    if raw_config.get("project_history") != old_history:
        save_raw_config(config_path, raw_config)


def _start_file_watcher(
    driver: Driver,
    raw_config: dict[str, Any],
    project_root: str,
    schedule_broadcast: Callable[[dict[str, Any]], None],
) -> Callable[[], None]:
    """Watch project files and push incremental graph updates over WebSocket.

    Returns a cleanup callable to stop the watcher (invoked on app shutdown).
    """
    from codegraph.watcher.file_watcher import CodeGraphWatcher
    from codegraph.watcher.incremental import update_file_in_graph

    def on_changes(paths: set[str]) -> None:
        for p in paths:
            try:
                update_file_in_graph(driver, project_root, p)
                schedule_broadcast({"type": "file_changed", "path": str(p)})
            except Exception as exc:
                logger.error("Error in watcher callback: %s", exc)

    exclude = raw_config.get("parser", {}).get("exclude_patterns", [])
    watcher = CodeGraphWatcher(project_root, on_changes, exclude_patterns=exclude)
    watcher.start()
    stop_poll = threading.Event()

    def _poll_watcher() -> None:
        while not stop_poll.is_set():
            watcher.check_for_changes()
            stop_poll.wait(0.5)

    threading.Thread(target=_poll_watcher, daemon=True).start()

    def stop_watcher() -> None:
        stop_poll.set()
        watcher.stop()

    return stop_watcher


def _mount_static(app: FastAPI, dev_mode: bool) -> None:
    """Serve built frontend assets and SPA fallback."""
    if dev_mode:
        return

    dist_dir = STATIC_DIR / "dist"
    if dist_dir.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(dist_dir / "assets")),
            name="assets",
        )

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str = ""):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)
        dist_index = STATIC_DIR / "dist" / "index.html"
        if dist_index.exists():
            return FileResponse(str(dist_index))
        return JSONResponse(
            {"error": "Frontend not built. Run: cd frontend && npm run build"},
            status_code=404,
        )
