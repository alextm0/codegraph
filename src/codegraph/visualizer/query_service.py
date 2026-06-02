"""Visualizer query and project helper logic."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from neo4j import Driver

from codegraph.visualizer.models import (
    BM25FileResult,
    PPREntityResult,
    QueryResponse,
    SeedInfo,
)


def get_git_info(project_root: str) -> dict[str, str]:
    """Fetch current git branch and commit hash for the target project."""
    try:
        root_path = Path(project_root).resolve()
        repo_name = root_path.name
        branch = (
            subprocess.check_output(
                ["git", "branch", "--show-current"], cwd=str(root_path)
            )
            .decode()
            .strip()
        )
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=str(root_path)
            )
            .decode()
            .strip()
        )
        return {"repo": f"{repo_name} @ {branch}", "commit": commit}
    except Exception:
        repo_name = Path(project_root).resolve().name if project_root else "unknown"
        return {"repo": repo_name, "commit": "unknown"}


def bm25_file_results(driver: Driver, task: str, top_k: int) -> list[BM25FileResult]:
    """Return file-level BM25 baseline ranks for PPR comparison."""
    from evaluation.baselines import BM25Baseline

    files = BM25Baseline().run(driver, task, k=top_k)
    return [
        BM25FileResult(rank=rank, file_path=fp)
        for rank, fp in enumerate(files, start=1)
    ]


def run_query(
    driver: Driver,
    raw_config: dict[str, Any],
    task: str,
    top_k: int,
) -> QueryResponse:
    """Run PPR + BM25 + subgraph, return a QueryResponse."""
    from codegraph.core.graph.ppr import PPRConfig, create_gds_client
    from codegraph.core.graph.queries import get_subgraph_for_nodes
    from codegraph.core.retrieval.explanations import build_explained_results
    from codegraph.core.retrieval.pipeline import run_core_retrieval
    from codegraph.utils.config import parse_signal_weights
    from codegraph.utils.graph_helpers import fetch_seed_names

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
    seed_ids = list(seeds.seeds.keys())
    seed_names = fetch_seed_names(driver, seed_ids)

    def _signal_label(source: str) -> str:
        if source == "entity_match":
            return "entity"
        if source == "current_file":
            return "file"
        return "bm25"

    seeds_out = [
        SeedInfo(
            id=seeds.metadata[nid]["qname"],
            name=seed_names.get(nid, str(nid)),
            signal=_signal_label(seeds.metadata[nid]["source"]),
            weight=round(weight, 4),
        )
        for nid, weight in sorted(seeds.seeds.items(), key=lambda x: -x[1])
    ]

    explained = build_explained_results(driver, core_result, top_k=top_k)
    ppr_out = [
        PPREntityResult(
            rank=item.rank,
            qualified_name=item.qualified_name,
            name=item.name,
            label=item.label,
            file_path=item.file_path,
            score=round(item.ppr_score, 5),
            path=item.reasoning_path,
            path_ids=list(item.path_ids),
            line_number=item.line_start,
            line_end=item.line_end,
            seed_qualified_names=list(item.seed_qualified_names),
            seed_sources=list(item.seed_sources),
            contribution=item.contribution,
        )
        for item in explained
    ]

    all_qnames: list[str] = [m["qname"] for m in seeds.metadata.values()]
    for r in ppr_out:
        all_qnames.append(r.qualified_name)
        all_qnames.extend(r.path_ids)
    all_qnames = list(dict.fromkeys(all_qnames))

    subgraph = get_subgraph_for_nodes(driver, all_qnames)
    ppr_score_by_qname = {
        r.qualified_name: r.score
        for r in core_result.ppr_results
        if r.qualified_name
    }
    path_ids_by_qname = {p.qualified_name: p.path_ids for p in ppr_out}
    seed_weight_by_qname = {
        seeds.metadata[nid]["qname"]: weight for nid, weight in seeds.seeds.items()
    }

    annotated_nodes = [
        {
            **node,
            "ppr_score": round(ppr_score_by_qname.get(node["id"], 0.0), 5),
            "is_seed": node["id"] in seed_weight_by_qname,
            "seed_weight": round(seed_weight_by_qname.get(node["id"], 0.0), 4),
            "reasoning_path": path_ids_by_qname.get(node["id"], []),
            "line_number": node.get("line_number", 0),
            "line_end": node.get("line_end", 0),
        }
        for node in subgraph["nodes"]
    ]

    return QueryResponse(
        seeds=seeds_out,
        ppr_results=ppr_out,
        bm25_results=bm25_file_results(driver, task, top_k),
        graph={"nodes": annotated_nodes, "edges": subgraph["edges"]},
        damping_factor=damping_factor,
        top_k=top_k,
        git_info=get_git_info(raw_config.get("project_root", ".")),
    )


def update_project_history(
    raw_config: dict, target_path: str, url: str | None = None
) -> None:
    """Add a project to history with path deduplication."""
    from codegraph.utils.paths import resolve_absolute_path

    try:
        abs_target = str(Path(target_path).resolve())
    except Exception:
        abs_target = target_path

    history = raw_config.get("project_history") or []
    history = [
        h
        for h in history
        if resolve_absolute_path(h.get("path", "")) != abs_target
    ]
    history.insert(
        0,
        {"name": Path(abs_target).name, "path": abs_target, "url": url},
    )
    raw_config["project_history"] = history[:5]


def run_dependencies_graph(
    driver: Driver,
    entity: str,
    direction: str = "both",
    depth: int = 1,
) -> dict[str, list[dict]]:
    """Return a focused subgraph for an entity and its dependencies."""
    from codegraph.core.graph.queries import (
        get_subgraph_for_nodes,
        query_entity_dependencies,
    )

    deps = query_entity_dependencies(driver, entity, direction, depth)
    qnames = list({entity, *(d.qualified_name for d in deps if d.qualified_name)})
    return get_subgraph_for_nodes(driver, qnames)
