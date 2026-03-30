"""FastAPI application factory for the CodeGraph visualizer.

Start via: codegraph visualize
"""

# NOTE: Do NOT add `from __future__ import annotations` here.
# FastAPI uses typing.get_type_hints() to resolve route parameter types from
# the module's global namespace. PEP 563 (future annotations) turns all
# annotations into strings, which breaks resolution for module-level classes.

import logging
import sys
from pathlib import Path
from typing import Any

from neo4j import Driver
from pydantic import BaseModel

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Pydantic models — must be at module level so FastAPI can resolve annotations
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    task: str
    top_k: int = 10


class SeedInfo(BaseModel):
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


class FileEntry(BaseModel):
    path: str
    type: str  # "file" or "directory"


class TreeResponse(BaseModel):
    root: str
    project_root: str
    files: list[FileEntry]


class StatsResponse(BaseModel):
    node_counts: dict[str, int]
    edge_counts: dict[str, int]
    total_nodes: int
    total_edges: int


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
    from codegraph.core.retrieval.seed_selection import extract_seeds, prepare_bm25_index
    from codegraph.core.graph.ppr import PPRConfig, create_gds_client, run_ppr_from_node_ids
    from codegraph.core.retrieval.pipeline import ensure_graph_ready
    from codegraph.core.graph.queries import trace_path_to_seed, get_subgraph_for_nodes

    # Build seeds
    bm25_index, searchable_nodes = prepare_bm25_index(driver)
    seeds = extract_seeds(
        driver,
        task_description=task,
        bm25_index=bm25_index,
        searchable_nodes=searchable_nodes,
    )

    seed_ids = list(seeds.seeds.keys())
    seed_names = _fetch_seed_names(driver, seed_ids)
    seed_qnames = _fetch_seed_qualified_names(driver, seed_ids)

    # Format seed info
    seeds_out = [
        SeedInfo(
            name=seed_names.get(nid, str(nid)),
            signal="entity" if weight >= 0.3 else "bm25",
            weight=round(weight, 4),
        )
        for nid, weight in sorted(seeds.seeds.items(), key=lambda x: -x[1])
    ]

    # Run PPR
    ppr_section = raw_config.get("ppr", {})
    ppr_config = PPRConfig(
        damping_factor=ppr_section.get("damping_factor", 0.70),
        max_iterations=ppr_section.get("max_iterations", 20),
        tolerance=ppr_section.get("tolerance", 1e-7),
        top_k=ppr_section.get("top_k", 30),
    )
    gds = create_gds_client(driver)
    ensure_graph_ready(driver, gds)
    ppr_results_raw = run_ppr_from_node_ids(gds, driver, seeds.seeds, ppr_config)

    # Deduplicate by file_path
    best_per_file: dict[str, float] = {}
    for r in ppr_results_raw:
        if r.file_path and (r.file_path not in best_per_file or r.score > best_per_file[r.file_path]):
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

    # BM25 baseline
    try:
        _add_evaluation_to_path()
        from evaluation.baselines import BM25Baseline  # type: ignore[import]
        bm25_files = BM25Baseline().run(driver, task, k=top_k)
    except ImportError:
        logger.warning("BM25Baseline not available (evaluation package not on path)")
        bm25_files = []

    bm25_out = [BM25FileResult(rank=i + 1, file_path=fp) for i, fp in enumerate(bm25_files)]

    # Build D3 subgraph from seed + PPR entity qualified_names
    all_qnames: list[str] = [qn for qn in seed_qnames.values() if qn]
    for r in ppr_results_raw:
        if r.qualified_name:
            all_qnames.append(r.qualified_name)
    all_qnames = list(dict.fromkeys(all_qnames))  # deduplicate, preserve order

    subgraph = get_subgraph_for_nodes(driver, all_qnames)

    ppr_score_by_qname = {r.qualified_name: r.score for r in ppr_results_raw if r.qualified_name}
    seed_weight_by_qname = {qn: seeds.seeds[nid] for nid, qn in seed_qnames.items() if qn}

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
        bm25_results=bm25_out,
        graph={"nodes": annotated_nodes, "edges": subgraph["edges"]},
    )


def _build_tree(project_root: str, raw_config: dict[str, Any]) -> TreeResponse:
    """Walk project_root for .py files, return a flat FileEntry list with dirs."""
    root_path = Path(project_root)

    exclude_patterns: list[str] = []
    exclude_patterns += raw_config.get("parser", {}).get("exclude_patterns", [])
    exclude_patterns += raw_config.get("exclude_patterns", [])

    def _is_excluded(path: Path) -> bool:
        """Return True if any part of the path matches an exclude pattern."""
        for part in path.parts:
            for pattern in exclude_patterns:
                if part == pattern or part.startswith(pattern.rstrip("/")):
                    return True
        return False

    seen_dirs: set[str] = set()
    entries: list[FileEntry] = []

    for py_file in sorted(root_path.rglob("*.py")):
        rel = py_file.relative_to(root_path)
        if _is_excluded(rel):
            continue

        # Add parent directories (deduplicated)
        for parent in reversed(rel.parents):
            if parent == Path("."):
                continue
            dir_str = str(parent)
            if dir_str not in seen_dirs:
                seen_dirs.add(dir_str)
                entries.append(FileEntry(path=dir_str, type="directory"))

        entries.append(FileEntry(path=str(rel), type="file"))

    return TreeResponse(
        root=str(root_path.name),
        project_root=project_root,
        files=entries,
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    driver: Driver,
    raw_config: dict[str, Any],
    project_root: str = "",
    dev_mode: bool = False,
):
    """Create and return the FastAPI application.

    Args:
        driver: Active Neo4j driver (from the CLI database manager).
        raw_config: Raw YAML config dict (from load_raw_config).
        project_root: Absolute path to the project root (for /api/tree).
        dev_mode: If True, skip static file serving and SPA fallback (Vite
                  dev server handles the frontend separately).
    """
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as e:
        raise ImportError(
            "FastAPI is required for the visualizer. "
            "Install it with: pip install -e '.[visualizer]'"
        ) from e

    app = FastAPI(
        title="CodeGraph Visualizer",
        description="Interactive graph visualization for CodeGraph retrieval results.",
        version="0.1.0",
    )

    # Static files and SPA fallback — production mode only
    if not dev_mode:
        dist_dir = STATIC_DIR / "dist"
        if dist_dir.exists():
            app.mount(
                "/assets",
                StaticFiles(directory=str(dist_dir / "assets")),
                name="assets",
            )

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            """Serve index.html for all non-/api routes (SPA fallback)."""
            dist_index = STATIC_DIR / "dist" / "index.html"
            if dist_index.exists():
                return FileResponse(str(dist_index))
            return JSONResponse(
                {
                    "error": "Frontend not built. Run: cd frontend && npm run build"
                },
                status_code=404,
            )

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

    @app.get("/api/tree", response_model=TreeResponse)
    def tree():
        """Return a flat file list for the sidebar tree."""
        try:
            return _build_tree(project_root, raw_config)
        except Exception as e:
            logger.exception("Tree endpoint failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/stats", response_model=StatsResponse)
    def graph_stats():
        """Return graph node and edge counts."""
        try:
            from codegraph.core.graph.queries import count_nodes_by_label, count_edges_by_type
            node_counts = count_nodes_by_label(driver)
            edge_counts = count_edges_by_type(driver)
            return StatsResponse(
                node_counts=node_counts,
                edge_counts=edge_counts,
                total_nodes=sum(node_counts.values()),
                total_edges=sum(edge_counts.values()),
            )
        except Exception as e:
            logger.exception("Stats endpoint failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    return app
