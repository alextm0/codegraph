"""Structured retrieval trace for debugging and evaluation."""

from __future__ import annotations

from neo4j import Driver

from codegraph.core.graph.ppr import PPRConfig
from codegraph.core.retrieval.explanations import (
    build_explained_results,
    explained_result_to_dict,
)
from codegraph.core.retrieval.pipeline import RawRetrievalResult


def build_retrieval_trace(
    driver: Driver,
    core_result: RawRetrievalResult,
    ppr_config: PPRConfig,
    task: str,
    top_k: int = 10,
) -> dict:
    """Build a JSON-serializable trace of one retrieval run."""
    explained = build_explained_results(driver, core_result, top_k=top_k)
    return {
        "task": task,
        "ppr_config": {
            "damping_factor": ppr_config.damping_factor,
            "top_k": ppr_config.top_k,
            "retrieval_mode": ppr_config.retrieval_mode,
        },
        "seeds": [
            {
                "qualified_name": meta["qname"],
                "source": meta["source"],
                "weight": round(core_result.seeds.seeds[nid], 4),
            }
            for nid, meta in core_result.seeds.metadata.items()
        ],
        "reachable_subgraph_size": len(explained),
        "top_results": [explained_result_to_dict(e) for e in explained],
    }
