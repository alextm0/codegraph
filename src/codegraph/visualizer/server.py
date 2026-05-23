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


class QueryRequest(BaseModel):
    task: str
    top_k: int = 10


class SeedInfo(BaseModel):
    id: str  # qualified_name
    name: str
    signal: str  # "entity" or "bm25"
    weight: float


class PPRFileResult(BaseModel):
    rank: int
    file_path: str
    score: float
    path: str


class BM25FileResult(BaseModel):
    rank: int
    file_path: str


class QueryResponse(BaseModel):
    seeds: list[SeedInfo]
    ppr_results: list[PPRFileResult]
    bm25_results: list[BM25FileResult]
    graph: dict[str, list[dict]]
    damping_factor: float
    top_k: int


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
    from codegraph.core.retrieval.seed_selection import (
        extract_seeds,
        prepare_bm25_index,
        extract_entity_names,
    )
    from codegraph.core.graph.ppr import (
        PPRConfig,
        create_gds_client,
        run_ppr_from_node_ids,
    )
    from codegraph.core.retrieval.pipeline import ensure_graph_ready
    from codegraph.core.graph.queries import trace_path_to_seed, get_subgraph_for_nodes
    from codegraph.utils.config import parse_signal_weights

    # Step 1: Extract seeds with auto-augmentation (matches CLI pipeline)
    seed_section = raw_config.get("seed_selection", {})
    exclude_seed_paths = seed_section.get("exclude_seed_paths") or None
    signal_weights = parse_signal_weights(seed_section)

    # Auto-augment mentioned_entities from task text
    auto_entities = extract_entity_names(task)

    bm25_index, searchable_nodes = prepare_bm25_index(
        driver, exclude_paths=exclude_seed_paths
    )
    seeds = extract_seeds(
        driver,
        task_description=task,
        mentioned_entities=auto_entities,
        signal_weights=signal_weights,
        bm25_index=bm25_index,
        searchable_nodes=searchable_nodes,
        exclude_paths=exclude_seed_paths,
    )

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

    # Step 2: Configure PPR
    ppr_section = raw_config.get("ppr", {})
    damping_factor = ppr_section.get("damping_factor", 0.70)
    ppr_config = PPRConfig(
        damping_factor=damping_factor,
        max_iterations=ppr_section.get("max_iterations", 20),
        tolerance=ppr_section.get("tolerance", 1e-7),
        top_k=ppr_section.get("top_k", 30),
    )
    gds = create_gds_client(driver)
    ensure_graph_ready(driver, gds)

    # Step 3: Run PPR
    ppr_results_raw = run_ppr_from_node_ids(gds, driver, seeds.seeds, ppr_config)

    # Deduplicate by file_path for the list view (keeps UI clean)
    best_per_file: dict[str, float] = {}
    for r in ppr_results_raw:
        if r.file_path and (
            r.file_path not in best_per_file or r.score > best_per_file[r.file_path]
        ):
            best_per_file[r.file_path] = r.score
    top_files = sorted(best_per_file.items(), key=lambda x: -x[1])[:top_k]

    # Add reasoning paths
    ppr_out = [
        PPRFileResult(
            rank=rank,
            file_path=fp,
            score=round(score, 5),
            path=trace_path_to_seed(driver, seed_ids, fp),
        )
        for rank, (fp, score) in enumerate(top_files, start=1)
    ]

    # Step 4: Build D3 subgraph
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
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(
    driver: Driver,
    raw_config: dict[str, Any],
    project_root: str = "",
    dev_mode: bool = False,
    watch_mode: bool = False,
):
    """Create and return the FastAPI application."""
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

    @app.post("/api/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        """Run PPR + BM25 retrieval and return graph data for visualization."""
        try:
            return _run_query(driver, raw_config, req.task, req.top_k)
        except Exception as e:
            logger.exception("Query failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/health")
    def health():
        """Health check endpoint."""
        return {"status": "ok"}

    @app.get("/api/node/{qname:path}", response_model=NodeDetailResponse)
    def node_detail(qname: str):
        """Return full detail for a single node."""
        try:
            from codegraph.core.graph.queries import get_node_detail

            detail = get_node_detail(driver, qname)
            if not detail:
                raise HTTPException(status_code=404, detail=f"Node '{qname}' not found")

            source_snippet = None
            file_path = detail["node"].get("file_path")
            line_start = detail["node"].get("line_number", 0)
            line_end = detail["node"].get("end_line", 0)

            if file_path and project_root:
                full_path = Path(project_root) / file_path
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

            data = get_subgraph_by_prefix(driver, focus)
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
