"""FastAPI application factory for the CodeGraph visualizer.

Start via: codegraph visualize
"""

# NOTE: Do NOT add `from __future__ import annotations` here.
# FastAPI uses typing.get_type_hints() to resolve route parameter types from
# the module's global namespace. PEP 563 (future annotations) turns all
# annotations into strings, which breaks resolution for module-level classes.

import logging
import sys
import asyncio
import threading
from pathlib import Path
from typing import Any

from neo4j import Driver
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Pydantic models — must be at module level so FastAPI can resolve annotations
# ---------------------------------------------------------------------------


class InitRequest(BaseModel):
    target: str

class QueryRequest(BaseModel):
    task: str
    top_k: int = 10


class SeedInfo(BaseModel):
    id: str  # qualified_name
    name: str
    signal: str  # "entity" or "bm25"
    weight: float


class PPREntityResult(BaseModel):
    rank: int
    qualified_name: str
    name: str
    label: str
    file_path: str
    score: float
    path: str
    path_ids: list[str] = []
    line_number: int = 0
    line_end: int = 0


class BM25FileResult(BaseModel):
    rank: int
    file_path: str


class QueryResponse(BaseModel):
    seeds: list[SeedInfo]
    ppr_results: list[PPREntityResult]
    bm25_results: list[BM25FileResult]
    graph: dict[str, list[dict]]
    damping_factor: float
    top_k: int
    git_info: dict[str, str] = {}


class NodeRelation(BaseModel):
    qualified_name: str
    name: str
    label: str
    file_path: str
    relationship: str


class NodeDetailResponse(BaseModel):
    node: dict[str, Any]
    incoming: list[NodeRelation]
    outgoing: list[NodeRelation]
    source_snippet: str | None = None


class SubgraphResponse(BaseModel):
    graph: dict[str, list[dict]]
    focus_path: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_seed_names(driver: Driver, seed_ids: list[int]) -> dict[int, str]:
    """Return {node_id: display_name} for a list of seed node IDs."""
    names: dict[int, str] = {}
    with driver.session() as session:
        result = session.run(
            "MATCH (n) WHERE id(n) IN $ids RETURN id(n) AS nid, "
            "coalesce(n.name, n.file_path, '') AS name",
            ids=seed_ids,
        )
        for r in result:
            names[r["nid"]] = r["name"] or ""
    return names


def _fetch_seed_qualified_names(driver: Driver, seed_ids: list[int]) -> dict[int, str]:
    """Return {node_id: qualified_name} for seed nodes."""
    qnames: dict[int, str] = {}
    with driver.session() as session:
        result = session.run(
            "MATCH (n) WHERE id(n) IN $ids RETURN id(n) AS nid, "
            "coalesce(n.qualified_name, n.file_path, '') AS qname",
            ids=seed_ids,
        )
        for r in result:
            qnames[r["nid"]] = r["qname"] or ""
    return qnames


def _add_evaluation_to_path() -> None:
    """Ensure the project root (containing evaluation/) is on sys.path."""
    project_root = str(Path(__file__).parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def _run_query(
    driver: Driver,
    raw_config: dict[str, Any],
    task: str,
    top_k: int,
) -> QueryResponse:
    """Core logic: run PPR + BM25 + subgraph, return a QueryResponse."""
    from codegraph.core.graph.ppr import (
        PPRConfig,
        create_gds_client,
    )
    from codegraph.core.retrieval.pipeline import run_core_retrieval
    from codegraph.core.graph.queries import (
        trace_path_to_seed,
        trace_path_ids_to_seed,
        get_subgraph_for_nodes,
    )
    from codegraph.utils.config import parse_signal_weights

    # Step 1: Configure PPR
    ppr_section = raw_config.get("ppr", {})
    damping_factor = ppr_section.get("damping_factor", 0.70)
    ppr_config = PPRConfig(
        damping_factor=damping_factor,
        max_iterations=ppr_section.get("max_iterations", 20),
        tolerance=ppr_section.get("tolerance", 1e-7),
        top_k=ppr_section.get("top_k", 30),
    )

    seed_section = raw_config.get("seed_selection", {})
    exclude_seed_paths = seed_section.get("exclude_seed_paths") or None
    signal_weights = parse_signal_weights(seed_section)

    gds = create_gds_client(driver)

    # Step 2: Run Unified Retrieval Core
    core_result = run_core_retrieval(
        driver=driver,
        gds=gds,
        task_description=task,
        ppr_config=ppr_config,
        signal_weights=signal_weights,
        exclude_seed_paths=exclude_seed_paths,
    )

    if not core_result:
        return QueryResponse(
            seeds=[],
            ppr_results=[],
            bm25_results=[],
            graph={"nodes": [], "edges": []},
            damping_factor=damping_factor,
            top_k=top_k,
        )

    seeds = core_result.seeds
    ppr_results_raw = core_result.ppr_results

    # Use the same deduplication logic as the core pipeline to avoid redundant File results
    from codegraph.core.retrieval.post_processing import _deduplicate_file_entities
    deduped_results = _deduplicate_file_entities(ppr_results_raw)
    top_results = deduped_results[:top_k]

    seed_ids = list(seeds.seeds.keys())
    seed_names = _fetch_seed_names(driver, seed_ids)

    # Format seed info for the UI using preserved metadata
    seeds_out = [
        SeedInfo(
            id=seeds.metadata[nid]["qname"],
            name=seed_names.get(nid, str(nid)),
            signal="entity"
            if seeds.metadata[nid]["source"] == "entity_match"
            else "bm25",
            weight=round(weight, 4),
        )
        for nid, weight in sorted(seeds.seeds.items(), key=lambda x: -x[1])
    ]

    # Add reasoning paths and format as PPREntityResult
    ppr_out = [
        PPREntityResult(
            rank=rank,
            qualified_name=r.qualified_name,
            name=r.name,
            label=r.label,
            file_path=r.file_path,
            score=round(r.score, 5),
            path=trace_path_to_seed(driver, seed_ids, r.file_path),
            path_ids=trace_path_ids_to_seed(driver, seed_ids, r.file_path),
            line_number=r.line_start,
            line_end=r.line_end,
        )
        for rank, r in enumerate(top_results, start=1)
    ]

    # Step 3: Build D3 subgraph
    all_qnames: list[str] = [m["qname"] for m in seeds.metadata.values()]
    for r in ppr_results_raw:
        if r.qualified_name:
            all_qnames.append(r.qualified_name)
    all_qnames = list(dict.fromkeys(all_qnames))

    subgraph = get_subgraph_for_nodes(driver, all_qnames)

    ppr_score_by_qname = {
        r.qualified_name: r.score for r in ppr_results_raw if r.qualified_name
    }
    seed_weight_by_qname = {
        seeds.metadata[nid]["qname"]: weight for nid, weight in seeds.seeds.items()
    }

    annotated_nodes = [
        {
            **node,
            "ppr_score": round(ppr_score_by_qname.get(node["id"], 0.0), 5),
            "is_seed": node["id"] in seed_weight_by_qname,
            "seed_weight": round(seed_weight_by_qname.get(node["id"], 0.0), 4),
            "line_number": node.get("line_number", 0),
            "line_end": node.get("line_end", 0),
        }
        for node in subgraph["nodes"]
    ]

    return QueryResponse(
        seeds=seeds_out,
        ppr_results=ppr_out,
        bm25_results=[],  # Removed BM25 comparison as per user request
        graph={"nodes": annotated_nodes, "edges": subgraph["edges"]},
        damping_factor=damping_factor,
        top_k=top_k,
        git_info=_get_git_info(raw_config.get("project_root", ".")),
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _get_git_info(project_root: str) -> dict[str, str]:
    """Fetch current git branch and commit hash for the target project."""
    import subprocess
    from pathlib import Path

    try:
        root_path = Path(project_root).resolve()
        repo_name = root_path.name
        
        branch = (
            subprocess.check_output(["git", "branch", "--show-current"], cwd=str(root_path))
            .decode()
            .strip()
        )
        commit = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(root_path))
            .decode()
            .strip()
        )
        return {"repo": f"{repo_name} @ {branch}", "commit": commit}
    except Exception:
        repo_name = Path(project_root).resolve().name if project_root else "unknown"
        return {"repo": repo_name, "commit": "unknown"}


def _update_project_history(raw_config: dict, target_path: str, url: str | None = None) -> None:
    """Add a project to history with robust path normalization and deduplication."""
    from pathlib import Path
    
    try:
        abs_target = str(Path(target_path).resolve())
    except Exception:
        abs_target = target_path

    history = raw_config.get("project_history") or []
    
    # 1. Full deduplication: remove any existing entry pointing to the same physical folder
    # We use list comprehension with Path.resolve() for safety
    def get_abs(p):
        try:
            return str(Path(p).resolve())
        except Exception:
            return p

    history = [h for h in history if get_abs(h.get("path", "")) != abs_target]
    
    # 2. Add new entry to the top
    history.insert(0, {
        "name": Path(abs_target).name,
        "path": abs_target,
        "url": url
    })
    
    # 3. Limit to 5 most recent
    raw_config["project_history"] = history[:5]


def create_app(
    driver: Driver,
    raw_config: dict[str, Any],
    project_root: str = "",
    config_path: Path | None = None,
    dev_mode: bool = False,
    watch_mode: bool = False,
):
    """Create and return the FastAPI application."""
    # The directory where config.yaml lives is our stable 'Workspaces' base
    base_dir = config_path.parent if config_path else Path.cwd()

    # Ensure current project is in history and clean up duplicates
    if config_path and config_path.exists():
        from codegraph.utils.config import save_raw_config
        
        # 1. Global cleanup of existing history (deduplicate all)
        history = raw_config.get("project_history") or []
        cleaned_history = []
        seen_abs = set()
        
        def get_abs(p):
            try:
                return str(Path(p).resolve())
            except Exception:
                return p

        for item in history:
            abs_p = get_abs(item.get("path", ""))
            if abs_p not in seen_abs:
                seen_abs.add(abs_p)
                cleaned_history.append(item)
        
        raw_config["project_history"] = cleaned_history[:5]
        
        # 2. Add/Move current project to top
        old_history = list(raw_config.get("project_history") or [])
        _update_project_history(raw_config, project_root)
        
        # Only save if history actually changed
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

    # Store connected clients for broadcasting
    connected_clients: set[WebSocket] = set()

    async def broadcast(message: dict):
        if not connected_clients:
            return
        for client in list(connected_clients):
            try:
                await client.send_json(message)
            except Exception:
                connected_clients.remove(client)

    if watch_mode and project_root:
        from codegraph.watcher.file_watcher import CodeGraphWatcher
        from codegraph.watcher.incremental import update_file_in_graph

        def on_changes(paths: set[str]) -> None:
            for p in paths:
                try:
                    update_file_in_graph(driver, project_root, p)
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            broadcast({"type": "file_changed", "path": str(p)}),
                            loop,
                        )
                except Exception as e:
                    logger.error("Error in watcher callback: %s", e)

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

    @app.post("/api/init")
    def initialize_project(req: InitRequest):
        """Clone (if URL) and build the graph for a target path."""
        import subprocess
        from pathlib import Path
        try:
            target = req.target
            if target.startswith("http://") or target.startswith("https://"):
                repo_name = target.rstrip("/").split("/")[-1].replace(".git", "")
                
                # Dedicated folder for cloned projects to keep root clean
                projects_dir = base_dir / "projects"
                projects_dir.mkdir(exist_ok=True)
                
                clone_path = projects_dir / repo_name
                if not clone_path.exists():
                    subprocess.run(["git", "clone", target, str(clone_path)], check=True)
                else:
                    # If it already exists, pull the latest changes
                    subprocess.run(["git", "pull"], cwd=str(clone_path), check=True)
                target_path = str(clone_path)
            else:
                target_path = str(Path(target).resolve())
                
            from codegraph.cli.cli_helpers import rebuild_helper
            from codegraph.utils.config import save_raw_config
            
            # Use absolute path for target_path to ensure consistent comparison
            abs_target_path = str(Path(target_path).resolve())
            
            # Update config with new project root
            # Note: config_path was provided at app creation
            if not config_path:
                 raise HTTPException(status_code=500, detail="Config path not known by server")
                 
            raw_config["project_root"] = target_path
            
            # Maintain project history with helper
            _update_project_history(raw_config, target_path, url=target if target.startswith("http") else None)
            
            save_raw_config(config_path, raw_config)
            
            # Rebuild graph for the new target
            rebuild_helper(config_path)
            
            return {"status": "ok", "path": abs_target_path}
        except subprocess.CalledProcessError as e:
            logger.error("Failed to clone repository: %s", e)
            raise HTTPException(status_code=500, detail="Failed to clone repository") from e
        except Exception as e:
            logger.exception("Failed to initialize project via UI")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/api/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        """Run PPR + BM25 retrieval and return graph data for visualization."""
        try:
            from codegraph.core.graph.database import get_database_manager
            active_driver = get_database_manager().get_driver()
            return _run_query(active_driver, raw_config, req.task, req.top_k)
        except Exception as e:
            logger.exception("Query failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/health")
    def health():
        """Health check endpoint."""
        active_root = raw_config.get("project_root", project_root)
        return {
            "status": "ok", 
            "git_info": _get_git_info(active_root),
            "project_history": raw_config.get("project_history", [])
        }

    @app.post("/api/open")
    def open_file_in_ide(file_path: str, line: int = 1):
        """Open a file in an IDE at the specified line.
        
        Attempts to use available CLIs in order: Cursor, VS Code, PyCharm.
        """
        import subprocess
        import shutil

        try:
            full_path = Path(project_root) / file_path
            if not full_path.exists():
                raise HTTPException(status_code=404, detail="File not found")

            # Try Cursor first (common for AI dev)
            if shutil.which("cursor"):
                cmd = ["cursor", "--goto", f"{full_path}:{line}"]
            # Then VS Code
            elif shutil.which("code"):
                cmd = ["code", "--goto", f"{full_path}:{line}"]
            # Then PyCharm (usually 'charm' or 'pycharm')
            elif shutil.which("charm"):
                cmd = ["charm", "--line", str(line), str(full_path)]
            elif shutil.which("pycharm"):
                cmd = ["pycharm", "--line", str(line), str(full_path)]
            else:
                # Fallback to system default 'open' (macOS) or 'xdg-open' (Linux)
                # Note: These usually don't support line numbers easily
                if shutil.which("open"):
                    cmd = ["open", str(full_path)]
                elif shutil.which("xdg-open"):
                    cmd = ["xdg-open", str(full_path)]
                else:
                    raise HTTPException(
                        status_code=500, 
                        detail="No supported IDE CLI found (cursor, code, charm, pycharm)"
                    )

            subprocess.run(cmd, check=True)
            return {"status": "ok", "command": " ".join(cmd)}
        except subprocess.CalledProcessError as e:
            logger.error("Failed to open file in IDE: %s", e)
            raise HTTPException(
                status_code=500, detail=f"IDE CLI failed: {' '.join(cmd)}"
            ) from e
        except Exception as e:
            logger.exception("Unexpected error opening file")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/graph/base")
    def get_base_graph():
        """Return the entire graph of the repository."""
        try:
            from codegraph.core.graph.queries import get_full_graph
            from codegraph.core.graph.database import get_database_manager

            active_driver = get_database_manager().get_driver()
            data = get_full_graph(active_driver)
            return data
        except Exception as e:
            logger.exception("Base graph endpoint failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/node/{qname:path}", response_model=NodeDetailResponse)
    def node_detail(qname: str):
        """Return full detail for a single node."""
        try:
            from codegraph.core.graph.queries import get_node_detail
            from codegraph.core.graph.database import get_database_manager

            active_driver = get_database_manager().get_driver()
            detail = get_node_detail(active_driver, qname)
            if not detail:
                raise HTTPException(status_code=404, detail=f"Node '{qname}' not found")

            source_snippet = None
            file_path = detail["node"].get("file_path")
            line_start = detail["node"].get("line_number", 0)
            line_end = detail["node"].get("end_line", 0)
            active_project_root = raw_config.get("project_root", project_root)

            if file_path and active_project_root:
                full_path = Path(active_project_root) / file_path
                if full_path.exists() and line_start > 0:
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            snippet_lines = lines[max(0, line_start - 1) : line_end]
                            source_snippet = "".join(snippet_lines)
                    except Exception:
                        pass

            detail["source_snippet"] = source_snippet
            return detail
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Node detail endpoint failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/subgraph", response_model=SubgraphResponse)
    def subgraph(focus: str):
        """Return a subgraph filtered by file_path prefix."""
        try:
            from codegraph.core.graph.queries import get_subgraph_by_prefix
            from codegraph.core.graph.database import get_database_manager

            active_driver = get_database_manager().get_driver()
            data = get_subgraph_by_prefix(active_driver, focus)
            return SubgraphResponse(graph=data, focus_path=focus)
        except Exception as e:
            logger.exception("Subgraph endpoint failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

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

    # Static files and SPA fallback — MUST be registered last so API routes take precedence
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
