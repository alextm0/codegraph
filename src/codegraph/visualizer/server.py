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


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(driver: Driver, raw_config: dict[str, Any]):
    """Create and return the FastAPI application.

    Args:
        driver: Active Neo4j driver (from the CLI database manager).
        raw_config: Raw YAML config dict (from load_raw_config).
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

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        """Serve the single-page frontend."""
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            return JSONResponse(
                {"error": "Frontend not found. index.html is missing."},
                status_code=404,
            )
        return FileResponse(str(index_path))

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

    return app
