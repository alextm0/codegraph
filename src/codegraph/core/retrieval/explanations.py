"""Shared explainability logic for CLI, visualizer, and MCP."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from neo4j import Driver

from codegraph.core.graph.ppr import PPRResult
from codegraph.core.graph.queries import batch_trace_paths
from codegraph.core.retrieval.pipeline import RawRetrievalResult
from codegraph.core.retrieval.post_processing import _deduplicate_file_entities

logger = logging.getLogger(__name__)

_LEXICAL_SOURCES = frozenset({"entity_match", "bm25", "issue_hint"})


@dataclass(frozen=True)
class ExplainedResult:
    """One ranked retrieval result with seed provenance and reasoning path."""

    rank: int
    qualified_name: str
    name: str
    label: str
    file_path: str
    ppr_score: float
    line_start: int
    line_end: int
    seed_qualified_names: tuple[str, ...]
    seed_sources: tuple[str, ...]
    reasoning_path: str
    path_ids: tuple[str, ...]
    contribution: str  # lexical | graph | both


def _seed_info_for_path(
    path_ids: list[str],
    seeds_metadata: dict[int, dict[str, str]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Map path node IDs back to originating seed qualified names and sources."""
    qname_to_source: dict[str, str] = {
        meta["qname"]: meta["source"] for meta in seeds_metadata.values()
    }
    seed_qnames: list[str] = []
    seed_sources: list[str] = []
    for node_id in path_ids:
        if node_id in qname_to_source and node_id not in seed_qnames:
            seed_qnames.append(node_id)
            seed_sources.append(qname_to_source[node_id])
    if not seed_qnames and seeds_metadata:
        top_meta = next(iter(seeds_metadata.values()))
        seed_qnames = [top_meta["qname"]]
        seed_sources = [top_meta["source"]]
    return tuple(seed_qnames), tuple(seed_sources)


def _contribution_tag(path_str: str, seed_sources: tuple[str, ...]) -> str:
    """Classify whether a result came from lexical seeds, graph propagation, or both."""
    has_lexical = any(s in _LEXICAL_SOURCES for s in seed_sources)
    if path_str == "direct seed":
        return "lexical" if has_lexical else "graph"
    if has_lexical and path_str not in ("(no path traced)", "(trace error)"):
        return "both"
    return "graph"


def build_explained_results(
    driver: Driver,
    core_result: RawRetrievalResult,
    top_k: int,
    dedupe_by: Literal["entity", "file"] = "entity",
) -> list[ExplainedResult]:
    """Build explained results from a core retrieval run using batch path tracing."""
    ppr_results = core_result.ppr_results
    seeds = core_result.seeds

    if dedupe_by == "file":
        ranked = _deduplicate_file_entities(ppr_results)[:top_k]
    else:
        ranked = ppr_results[:top_k]

    seed_ids = list(seeds.seeds.keys())
    target_ids = [r.qualified_name for r in ranked if r.qualified_name]
    traced = batch_trace_paths(driver, seed_ids, target_ids)

    explained: list[ExplainedResult] = []
    for rank, result in enumerate(ranked, start=1):
        trace = traced.get(result.qualified_name, {})
        path_str = trace.get("path_str", "(no path traced)")
        path_ids = trace.get("path_ids", [])
        seed_qnames, seed_sources = _seed_info_for_path(path_ids, seeds.metadata)
        if path_str == "direct seed":
            meta = next(
                (
                    m
                    for m in seeds.metadata.values()
                    if m["qname"] == result.qualified_name
                ),
                None,
            )
            if meta:
                seed_qnames = (meta["qname"],)
                seed_sources = (meta["source"],)

        explained.append(
            ExplainedResult(
                rank=rank,
                qualified_name=result.qualified_name,
                name=result.name,
                label=result.label,
                file_path=result.file_path,
                ppr_score=result.score,
                line_start=result.line_start,
                line_end=result.line_end,
                seed_qualified_names=seed_qnames,
                seed_sources=seed_sources,
                reasoning_path=path_str,
                path_ids=tuple(path_ids),
                contribution=_contribution_tag(path_str, seed_sources),
            )
        )
    return explained


def explained_result_to_dict(item: ExplainedResult) -> dict:
    """Serialize an ExplainedResult for JSON APIs."""
    return {
        "rank": item.rank,
        "qualified_name": item.qualified_name,
        "name": item.name,
        "label": item.label,
        "file_path": item.file_path,
        "ppr_score": round(item.ppr_score, 5),
        "lines": [item.line_start, item.line_end],
        "seed_qualified_names": list(item.seed_qualified_names),
        "seed_sources": list(item.seed_sources),
        "reasoning_path": item.reasoning_path,
        "path_ids": list(item.path_ids),
        "contribution": item.contribution,
    }
