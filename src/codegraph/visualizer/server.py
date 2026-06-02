"""FastAPI application factory for the CodeGraph visualizer.

Start via: codegraph visualize
"""

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any

from neo4j import Driver
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from codegraph.visualizer.models import (
    DependenciesResponse,
    DependencyResult,
    InitRequest,
    NodeDetailResponse,
    QueryRequest,
    QueryResponse,
    SubgraphResponse,
)
from codegraph.visualizer.query_service import (
    get_git_info,
    run_query,
    update_project_history,
)

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    driver: Driver,
    raw_config: dict[str, Any],
    project_root: str = "",
    config_path: Path | None = None,
    dev_mode: bool = False,
    watch_mode: bool = False,
):
    """Create and return the FastAPI application."""
    base_dir = config_path.parent if config_path else Path.cwd()

    if config_path and config_path.exists():
        from codegraph.utils.config import save_raw_config
        from codegraph.utils.paths import resolve_absolute_path

        history = raw_config.get("project_history") or []
        cleaned_history = []
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

    app = FastAPI(
        title="CodeGraph Visualizer",
        description="Interactive graph visualization for CodeGraph retrieval results.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    connected_clients: set[WebSocket] = set()
    index_lock = threading.Lock()
    indexing_in_progress = {"value": False}

    async def broadcast(message: dict) -> None:
        if not connected_clients:
            return
        for client in list(connected_clients):
            try:
                await client.send_json(message)
            except Exception:
                connected_clients.remove(client)

    def schedule_broadcast(message: dict) -> None:
        loop = getattr(app.state, "event_loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast(message), loop)

    @app.on_event("startup")
    async def capture_event_loop() -> None:
        app.state.event_loop = asyncio.get_running_loop()

    if watch_mode and project_root:
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
        _stop_poll = threading.Event()

        def _poll_watcher() -> None:
            while not _stop_poll.is_set():
                watcher.check_for_changes()
                _stop_poll.wait(0.5)

        threading.Thread(target=_poll_watcher, daemon=True).start()

        @app.on_event("shutdown")
        def stop_watcher() -> None:
            _stop_poll.set()
            watcher.stop()

    def _resolve_target_path(target: str) -> str:
        import subprocess

        if target.startswith("http://") or target.startswith("https://"):
            repo_name = target.rstrip("/").split("/")[-1].replace(".git", "")
            projects_dir = base_dir / "projects"
            projects_dir.mkdir(exist_ok=True)
            clone_path = projects_dir / repo_name
            if not clone_path.exists():
                subprocess.run(
                    ["git", "clone", target, str(clone_path)], check=True
                )
            else:
                subprocess.run(["git", "pull"], cwd=str(clone_path), check=True)
            return str(clone_path)
        return str(Path(target).resolve())

    @app.post("/api/init")
    def initialize_project(req: InitRequest):
        """Clone (if URL) and rebuild the graph in the background."""
        import subprocess

        with index_lock:
            if indexing_in_progress["value"]:
                raise HTTPException(
                    status_code=409, detail="Indexing already in progress"
                )
            indexing_in_progress["value"] = True

        try:
            if not config_path:
                raise HTTPException(
                    status_code=500, detail="Config path not known by server"
                )

            target_path = _resolve_target_path(req.target)
            abs_target_path = str(Path(target_path).resolve())

            from codegraph.utils.config import save_raw_config

            raw_config["project_root"] = target_path
            update_project_history(
                raw_config,
                target_path,
                url=req.target if req.target.startswith("http") else None,
            )
            save_raw_config(config_path, raw_config)

            def _rebuild_job() -> None:
                try:
                    schedule_broadcast(
                        {"type": "rebuild_started", "path": abs_target_path}
                    )
                    from codegraph.cli.cli_helpers import rebuild_helper

                    rebuild_helper(config_path)
                    schedule_broadcast(
                        {
                            "type": "rebuild_complete",
                            "path": abs_target_path,
                            "git_info": get_git_info(target_path),
                        }
                    )
                except Exception as exc:
                    logger.exception("Background rebuild failed")
                    schedule_broadcast(
                        {"type": "rebuild_error", "detail": str(exc)}
                    )
                finally:
                    with index_lock:
                        indexing_in_progress["value"] = False

            threading.Thread(target=_rebuild_job, daemon=True).start()
            return {"status": "started", "path": abs_target_path}
        except subprocess.CalledProcessError as exc:
            with index_lock:
                indexing_in_progress["value"] = False
            logger.error("Failed to clone repository: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to clone repository"
            ) from exc
        except HTTPException:
            with index_lock:
                indexing_in_progress["value"] = False
            raise
        except Exception as exc:
            with index_lock:
                indexing_in_progress["value"] = False
            logger.exception("Failed to initialize project via UI")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        """Run PPR + BM25 retrieval and return graph data for visualization."""
        try:
            from codegraph.core.graph.database import get_database_manager

            active_driver = get_database_manager().get_driver()
            return run_query(active_driver, raw_config, req.task, req.top_k)
        except Exception as exc:
            logger.exception("Query failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/health")
    def health():
        """Health check endpoint."""
        active_root = raw_config.get("project_root", project_root)
        return {
            "status": "ok",
            "git_info": get_git_info(active_root),
            "project_history": raw_config.get("project_history", []),
        }

    @app.get("/api/stats")
    def stats():
        """Return node and edge counts by type."""
        try:
            from codegraph.core.graph.database import get_database_manager
            from codegraph.core.graph.queries import (
                count_edges_by_type,
                count_nodes_by_label,
            )

            active_driver = get_database_manager().get_driver()
            return {
                "nodes": count_nodes_by_label(active_driver),
                "edges": count_edges_by_type(active_driver),
            }
        except Exception as exc:
            logger.exception("Stats endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/dependencies", response_model=DependenciesResponse)
    def dependencies(entity: str, direction: str = "both", depth: int = 1):
        """Return upstream/downstream dependencies for an entity."""
        try:
            from codegraph.core.graph.database import get_database_manager
            from codegraph.core.graph.queries import query_entity_dependencies

            active_driver = get_database_manager().get_driver()
            nodes = query_entity_dependencies(
                active_driver, entity, direction, depth
            )
            return DependenciesResponse(
                entity=entity,
                direction=direction,
                depth=depth,
                results=[
                    DependencyResult(
                        qualified_name=n.qualified_name,
                        name=n.name,
                        label=n.label,
                        file_path=n.file_path,
                        relationship_type=n.relationship_type or "",
                    )
                    for n in nodes
                ],
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Dependencies endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/open")
    def open_file_in_ide(file_path: str, line: int = 1):
        """Open a file in an IDE at the specified line."""
        import shutil
        import subprocess

        try:
            active_root = raw_config.get("project_root", project_root)
            full_path = Path(active_root) / file_path
            if not full_path.exists():
                raise HTTPException(status_code=404, detail="File not found")

            if shutil.which("cursor"):
                cmd = ["cursor", "--goto", f"{full_path}:{line}"]
            elif shutil.which("code"):
                cmd = ["code", "--goto", f"{full_path}:{line}"]
            elif shutil.which("charm"):
                cmd = ["charm", "--line", str(line), str(full_path)]
            elif shutil.which("pycharm"):
                cmd = ["pycharm", "--line", str(line), str(full_path)]
            elif shutil.which("open"):
                cmd = ["open", str(full_path)]
            elif shutil.which("xdg-open"):
                cmd = ["xdg-open", str(full_path)]
            else:
                raise HTTPException(
                    status_code=500,
                    detail="No supported IDE CLI found (cursor, code, charm, pycharm)",
                )

            subprocess.run(cmd, check=True)
            return {"status": "ok", "command": " ".join(cmd)}
        except subprocess.CalledProcessError as exc:
            logger.error("Failed to open file in IDE: %s", exc)
            raise HTTPException(
                status_code=500, detail=f"IDE CLI failed: {' '.join(cmd)}"
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error opening file")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/graph/base")
    def get_base_graph():
        """Return the entire graph of the repository."""
        try:
            from codegraph.core.graph.database import get_database_manager
            from codegraph.core.graph.queries import get_full_graph

            active_driver = get_database_manager().get_driver()
            return get_full_graph(active_driver)
        except Exception as exc:
            logger.exception("Base graph endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/node/{qname:path}", response_model=NodeDetailResponse)
    def node_detail(qname: str):
        """Return full detail for a single node."""
        try:
            from codegraph.core.graph.database import get_database_manager
            from codegraph.core.graph.queries import get_node_detail

            active_driver = get_database_manager().get_driver()
            detail = get_node_detail(active_driver, qname)
            if not detail:
                raise HTTPException(
                    status_code=404, detail=f"Node '{qname}' not found"
                )

            source_snippet = None
            file_path = detail["node"].get("file_path")
            line_start = detail["node"].get("line_number", 0)
            line_end = detail["node"].get("end_line", 0)
            active_project_root = raw_config.get("project_root", project_root)

            if file_path and active_project_root:
                full_path = Path(active_project_root) / file_path
                if full_path.exists() and line_start > 0:
                    try:
                        with open(full_path, encoding="utf-8") as f:
                            lines = f.readlines()
                            source_snippet = "".join(
                                lines[max(0, line_start - 1) : line_end]
                            )
                    except Exception:
                        pass

            detail["source_snippet"] = source_snippet
            return detail
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Node detail endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/subgraph", response_model=SubgraphResponse)
    def subgraph(focus: str):
        """Return a subgraph filtered by file_path prefix."""
        try:
            from codegraph.core.graph.database import get_database_manager
            from codegraph.core.graph.queries import get_subgraph_by_prefix

            active_driver = get_database_manager().get_driver()
            data = get_subgraph_by_prefix(active_driver, focus)
            return SubgraphResponse(graph=data, focus_path=focus)
        except Exception as exc:
            logger.exception("Subgraph endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.websocket("/ws/status")
    async def websocket_status(websocket: WebSocket):
        await websocket.accept()
        connected_clients.add(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            connected_clients.remove(websocket)
        except Exception:
            if websocket in connected_clients:
                connected_clients.remove(websocket)

    if not dev_mode:
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
            """Serve index.html for all non-/api routes (SPA fallback)."""
            if full_path.startswith("api/") or full_path.startswith("ws/"):
                raise HTTPException(status_code=404)
            dist_index = STATIC_DIR / "dist" / "index.html"
            if dist_index.exists():
                return FileResponse(str(dist_index))
            return JSONResponse(
                {"error": "Frontend not built. Run: cd frontend && npm run build"},
                status_code=404,
            )

    return app
