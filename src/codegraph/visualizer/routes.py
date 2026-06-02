"""FastAPI route handlers for the CodeGraph visualizer."""

from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from neo4j import Driver

from codegraph.visualizer.context import VisualizerContext
from codegraph.visualizer.models import (
    DependenciesGraphResponse,
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
    run_dependencies_graph,
    run_query,
    update_project_history,
)

logger = logging.getLogger(__name__)


def register_routes(
    app: FastAPI,
    ctx: VisualizerContext,
    connected_clients: set[WebSocket],
) -> None:
    """Attach all /api and /ws routes to the FastAPI app."""

    def _resolve_target_path(target: str) -> str:
        if target.startswith("http://") or target.startswith("https://"):
            repo_name = target.rstrip("/").split("/")[-1].replace(".git", "")
            projects_dir = ctx.base_dir / "projects"
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
        with ctx.index_lock:
            if ctx.indexing_in_progress["value"]:
                raise HTTPException(
                    status_code=409, detail="Indexing already in progress"
                )
            ctx.indexing_in_progress["value"] = True

        try:
            if not ctx.config_path:
                raise HTTPException(
                    status_code=500, detail="Config path not known by server"
                )

            target_path = _resolve_target_path(req.target)
            abs_target_path = str(Path(target_path).resolve())

            from codegraph.utils.config import save_raw_config

            ctx.raw_config["project_root"] = target_path
            update_project_history(
                ctx.raw_config,
                target_path,
                url=req.target if req.target.startswith("http") else None,
            )
            save_raw_config(ctx.config_path, ctx.raw_config)

            def _rebuild_job() -> None:
                try:
                    ctx.schedule_broadcast(
                        {"type": "rebuild_started", "path": abs_target_path}
                    )
                    from codegraph.cli.cli_helpers import rebuild_helper

                    def _on_progress(payload: dict) -> None:
                        ctx.schedule_broadcast(
                            {"type": "rebuild_progress", **payload}
                        )

                    rebuild_helper(ctx.config_path, progress_callback=_on_progress)
                    ctx.schedule_broadcast(
                        {
                            "type": "rebuild_complete",
                            "path": abs_target_path,
                            "git_info": get_git_info(target_path),
                        }
                    )
                except Exception as exc:
                    logger.exception("Background rebuild failed")
                    ctx.schedule_broadcast(
                        {"type": "rebuild_error", "detail": str(exc)}
                    )
                finally:
                    with ctx.index_lock:
                        ctx.indexing_in_progress["value"] = False

            threading.Thread(target=_rebuild_job, daemon=True).start()
            return {"status": "started", "path": abs_target_path}
        except subprocess.CalledProcessError as exc:
            with ctx.index_lock:
                ctx.indexing_in_progress["value"] = False
            logger.error("Failed to clone repository: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to clone repository"
            ) from exc
        except HTTPException:
            with ctx.index_lock:
                ctx.indexing_in_progress["value"] = False
            raise
        except Exception as exc:
            with ctx.index_lock:
                ctx.indexing_in_progress["value"] = False
            logger.exception("Failed to initialize project via UI")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        """Run PPR + BM25 retrieval and return graph data for visualization."""
        try:
            active_driver = _active_driver()
            return run_query(active_driver, ctx.raw_config, req.task, req.top_k)
        except Exception as exc:
            logger.exception("Query failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/health")
    def health():
        """Health check endpoint."""
        active_root = ctx.raw_config.get("project_root", ctx.project_root)
        return {
            "status": "ok",
            "git_info": get_git_info(active_root),
            "project_history": ctx.raw_config.get("project_history", []),
        }

    @app.get("/api/stats")
    def stats():
        """Return node and edge counts by type."""
        try:
            from codegraph.core.graph.queries import (
                count_edges_by_type,
                count_nodes_by_label,
            )

            active_driver = _active_driver()
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
            from codegraph.core.graph.queries import query_entity_dependencies

            active_driver = _active_driver()
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

    @app.get("/api/dependencies/graph", response_model=DependenciesGraphResponse)
    def dependencies_graph(entity: str, direction: str = "both", depth: int = 1):
        """Return a subgraph focused on an entity and its dependencies."""
        try:
            active_driver = _active_driver()
            graph = run_dependencies_graph(
                active_driver, entity, direction, depth
            )
            return DependenciesGraphResponse(
                entity=entity,
                direction=direction,
                depth=depth,
                graph=graph,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Dependencies graph endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/open")
    def open_file_in_ide(file_path: str, line: int = 1):
        """Open a file in an IDE at the specified line."""
        import shutil

        try:
            active_root = ctx.raw_config.get("project_root", ctx.project_root)
            full_path = Path(active_root) / file_path
            if not full_path.exists():
                raise HTTPException(status_code=404, detail="File not found")

            cmd = _ide_open_command(full_path, line)
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
            from codegraph.core.graph.queries import get_full_graph

            active_driver = _active_driver()
            return get_full_graph(active_driver)
        except Exception as exc:
            logger.exception("Base graph endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/node/{qname:path}", response_model=NodeDetailResponse)
    def node_detail(qname: str):
        """Return full detail for a single node."""
        try:
            from codegraph.core.graph.queries import get_node_detail

            active_driver = _active_driver()
            detail = get_node_detail(active_driver, qname)
            if not detail:
                raise HTTPException(
                    status_code=404, detail=f"Node '{qname}' not found"
                )

            source_snippet = None
            file_path = detail["node"].get("file_path")
            line_start = detail["node"].get("line_number", 0)
            line_end = detail["node"].get("end_line", 0)
            active_project_root = ctx.raw_config.get(
                "project_root", ctx.project_root
            )

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
            from codegraph.core.graph.queries import get_subgraph_by_prefix

            active_driver = _active_driver()
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

    def _active_driver() -> Driver:
        from codegraph.core.graph.database import get_database_manager

        return get_database_manager().get_driver()


def _ide_open_command(full_path: Path, line: int) -> list[str]:
    """Resolve IDE CLI command for opening a file at a line."""
    import shutil

    if shutil.which("cursor"):
        return ["cursor", "--goto", f"{full_path}:{line}"]
    if shutil.which("code"):
        return ["code", "--goto", f"{full_path}:{line}"]
    if shutil.which("charm"):
        return ["charm", "--line", str(line), str(full_path)]
    if shutil.which("pycharm"):
        return ["pycharm", "--line", str(line), str(full_path)]
    if shutil.which("open"):
        return ["open", str(full_path)]
    if shutil.which("xdg-open"):
        return ["xdg-open", str(full_path)]
    raise HTTPException(
        status_code=500,
        detail="No supported IDE CLI found (cursor, code, charm, pycharm)",
    )
