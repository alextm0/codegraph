"""FastAPI route handlers for the CodeGraph visualizer."""

from __future__ import annotations

import logging
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from neo4j import Driver

from codegraph.visualizer.context import VisualizerContext
from codegraph.visualizer.models import (
    DeadCodeResponse,
    DependenciesGraphResponse,
    DependenciesResponse,
    DependencyResult,
    DoctorResponse,
    FileEntitySummary,
    FileSourceResponse,
    InitRequest,
    NodeDetailResponse,
    QueryRequest,
    QueryResponse,
    SearchResponse,
    SearchResult,
    StatsResponse,
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

    def _start_rebuild_job(target_path: str) -> None:
        """Run rebuild in background and broadcast WS progress."""
        abs_target_path = str(Path(target_path).resolve())

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
                        "timestamp": datetime.now(UTC).isoformat(),
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
            ctx.project_root = abs_target_path
            update_project_history(
                ctx.raw_config,
                target_path,
                url=req.target if req.target.startswith("http") else None,
            )
            save_raw_config(ctx.config_path, ctx.raw_config)

            _start_rebuild_job(target_path)
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

    @app.post("/api/rebuild")
    def rebuild_current():
        """Rebuild the graph for the current project_root."""
        with ctx.index_lock:
            if ctx.indexing_in_progress["value"]:
                raise HTTPException(
                    status_code=409, detail="Indexing already in progress"
                )
            ctx.indexing_in_progress["value"] = True

        if not ctx.config_path:
            with ctx.index_lock:
                ctx.indexing_in_progress["value"] = False
            raise HTTPException(
                status_code=500, detail="Config path not known by server"
            )

        target_path = ctx.raw_config.get("project_root", ctx.project_root)
        _start_rebuild_job(str(target_path))
        return {"status": "started", "path": str(Path(target_path).resolve())}

    @app.post("/api/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        """Run PPR + BM25 retrieval and return graph data for visualization."""
        try:
            active_driver = _active_driver()
            return run_query(
                active_driver,
                ctx.raw_config,
                req.task,
                req.top_k,
                mentioned_entities=req.mentioned_entities,
                token_budget=req.token_budget,
            )
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

    @app.get("/api/stats", response_model=StatsResponse)
    def stats():
        """Return node and edge counts by type plus top files and last build."""
        try:
            from codegraph.cli.commands._shared import _read_build_timestamp
            from codegraph.core.graph.queries import (
                count_edges_by_type,
                count_nodes_by_label,
                get_most_connected_files,
            )

            active_driver = _active_driver()
            last_build = None
            if ctx.config_path:
                last_build = _read_build_timestamp(ctx.config_path)

            return StatsResponse(
                nodes=count_nodes_by_label(active_driver),
                edges=count_edges_by_type(active_driver),
                most_connected_files=get_most_connected_files(active_driver, limit=5),
                last_build=last_build,
            )
        except Exception as exc:
            logger.exception("Stats endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/search", response_model=SearchResponse)
    def search_nodes(q: str = ""):
        """Search entities by name or qualified_name pattern."""
        if not q.strip():
            return SearchResponse(results=[])
        try:
            from codegraph.core.graph.queries import find_node_by_pattern

            active_driver = _active_driver()
            nodes = find_node_by_pattern(active_driver, q.strip())
            return SearchResponse(
                results=[
                    SearchResult(
                        qualified_name=n.qualified_name,
                        name=n.name,
                        label=n.label,
                        file_path=n.file_path,
                    )
                    for n in nodes
                ]
            )
        except Exception as exc:
            logger.exception("Search endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/doctor", response_model=DoctorResponse)
    def doctor():
        """Run health diagnostics and return structured results."""
        try:
            from codegraph.cli.commands.doctor import run_doctor_checks

            result = run_doctor_checks(ctx.config_path)
            return DoctorResponse(**result)
        except Exception as exc:
            logger.exception("Doctor endpoint failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/dead-code", response_model=DeadCodeResponse)
    def dead_code(limit: int = 50):
        """Return uncalled functions and methods."""
        try:
            from codegraph.core.graph.queries import find_dead_code

            active_driver = _active_driver()
            results = find_dead_code(active_driver, limit)
            return DeadCodeResponse(
                results=[
                    {
                        "qualified_name": n.qualified_name,
                        "name": n.name,
                        "label": n.label,
                        "file_path": n.file_path,
                    }
                    for n in results
                ],
                total=len(results),
            )
        except Exception as exc:
            logger.exception("Dead code endpoint failed")
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
            from codegraph.visualizer.graph_filter import (
                config_exclude_patterns,
                filter_graph_for_visualizer,
            )

            return filter_graph_for_visualizer(
                get_full_graph(active_driver),
                config_exclude_patterns(ctx.raw_config),
            )
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

    @app.get("/api/files/source", response_model=FileSourceResponse)
    def file_source(file_path: str = ""):
        """Return full source text for a file under project_root."""
        if not file_path.strip():
            raise HTTPException(status_code=400, detail="file_path is required")
        try:
            from codegraph.core.graph.queries import get_file_contents
            from codegraph.core.graph.utils import normalize_path
            from codegraph.visualizer.file_source import resolve_source_file

            active_root = ctx.raw_config.get("project_root", ctx.project_root)
            rel = normalize_path(file_path.strip())
            disk_path = resolve_source_file(str(active_root), rel)
            content = disk_path.read_text(encoding="utf-8", errors="replace")
            entities = get_file_contents(_active_driver(), rel)
            return FileSourceResponse(
                file_path=rel,
                content=content,
                line_count=len(content.splitlines()),
                entities=[
                    FileEntitySummary(
                        qualified_name=e.qualified_name,
                        name=e.name,
                        label=e.label,
                        file_path=e.file_path,
                    )
                    for e in entities
                ],
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"File not found: {exc}") from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("File source endpoint failed")
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
