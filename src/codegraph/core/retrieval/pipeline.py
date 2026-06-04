"""Retrieval pipeline orchestration.

Design notes:
- Thin orchestrator: seeds extraction → IDF reweighting → GDS projection → PPR → formatting.
  All logic lives in seed_selection.py, post_processing.py, and ppr.py respectively.
- ensure_graph_ready() is called on every invocation to reapply IDF weights and recreate
  the GDS projection. Safe to call repeatedly — drop is a no-op if no projection exists.
"""

import logging
from dataclasses import dataclass
from typing import Any

from graphdatascience import GraphDataScience
from graphdatascience.graph.graph_object import Graph
from neo4j import Driver

from codegraph.core.graph.ppr import (
    PPRConfig,
    PPRResult,
    drop_projection,
    project_graph,
    run_ppr_from_node_ids,
)
from codegraph.core.retrieval.post_processing import (
    ContextResult,
    apply_idf_weights,
    format_context,
    reset_base_weights,
)
from codegraph.core.retrieval.seed_selection import (
    PersonalizationVector,
    extract_entity_names,
    extract_seeds,
    prepare_bm25_index,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawRetrievalResult:
    """Unified container for retrieval signals and PPR scores.
    
    Consumed by MCP/CLI (for context formatting) and Visualizer (for graph display).
    """
    seeds: PersonalizationVector
    ppr_results: list[PPRResult]


def run_core_retrieval(
    driver: Driver,
    gds: GraphDataScience,
    task_description: str,
    mentioned_entities: list[str] | None = None,
    ppr_config: PPRConfig | None = None,
    signal_weights: dict[str, float] | None = None,
    relationship_types: list[str] | None = None,
    orientation: str = "UNDIRECTED",
    apply_idf: bool = True,
    exclude_seed_paths: list[str] | None = None,
    bm25_index: Any | None = None,
    searchable_nodes: list[dict] | None = None,
    graph_ready: bool = False,
) -> RawRetrievalResult | None:
    """Core retrieval engine: seeds extraction -> PPR.

    This is the ground-truth retrieval logic used across all interfaces.

    Args:
        bm25_index: Optional pre-built BM25 index (e.g. SWE-bench group setup).
        searchable_nodes: Rows aligned with bm25_index.
        graph_ready: When True, skip ensure_graph_ready (projection already exists).
    """
    if ppr_config is None:
        ppr_config = PPRConfig()

    # Auto-augment mentioned_entities with identifiers extracted from the task text.
    auto_entities = extract_entity_names(task_description)
    existing = set(mentioned_entities or [])
    augmented_entities = list(mentioned_entities or []) + [
        e for e in auto_entities if e not in existing
    ]

    if bm25_index is None or searchable_nodes is None:
        bm25_index, searchable_nodes = prepare_bm25_index(
            driver, exclude_paths=exclude_seed_paths
        )

    # Step 1: Extract seeds from the task description.
    seeds = extract_seeds(
        driver,
        task_description=task_description,
        mentioned_entities=augmented_entities or None,
        signal_weights=signal_weights,
        bm25_index=bm25_index,
        searchable_nodes=searchable_nodes,
        exclude_paths=exclude_seed_paths,
    )
    if not seeds.seeds:
        logger.warning("Pipeline: no seeds found — returning empty context")
        return None

    # Step 2: Prepare the graph for PPR (IDF weights + fresh GDS projection).
    if not graph_ready:
        ensure_graph_ready(
            driver,
            gds,
            relationship_types=relationship_types,
            orientation=orientation,
            apply_idf=apply_idf,
        )

    # Step 3: Run Personalized PageRank (uniform mode uses equal restart per seed).
    ppr_results = run_ppr_from_node_ids(gds, driver, seeds.seeds, ppr_config)
    if not ppr_results:
        logger.warning("Pipeline: PPR returned no results")
        return None

    return RawRetrievalResult(seeds=seeds, ppr_results=ppr_results)


def file_paths_from_ppr_results(
    ppr_results: list[PPRResult],
    *,
    rank_by: str = "first_entity",
) -> list[str]:
    """Collapse entity-level PPR hits to an ordered file list for file-level metrics.

    Args:
        ppr_results: Ranked PPR output (highest score first).
        rank_by: ``first_entity`` preserves first-seen file order; ``max_score`` ranks
            files by the maximum entity score in that file.
    """
    if rank_by == "max_score":
        best: dict[str, float] = {}
        for result in ppr_results:
            if not result.file_path:
                continue
            prev = best.get(result.file_path, -1.0)
            if result.score > prev:
                best[result.file_path] = result.score
        return sorted(best, key=best.get, reverse=True)

    return list(dict.fromkeys(r.file_path for r in ppr_results if r.file_path))


def run_retrieval_pipeline(
    driver: Driver,
    gds: GraphDataScience,
    task_description: str,
    project_root: str,
    mentioned_entities: list[str] | None = None,
    ppr_config: PPRConfig | None = None,
    signal_weights: dict[str, float] | None = None,
    token_budget: int = 6000,
    relationship_types: list[str] | None = None,
    orientation: str = "UNDIRECTED",
    apply_idf: bool = True,
    exclude_seed_paths: list[str] | None = None,
) -> list[ContextResult]:
    """Run the full retrieval pipeline and return context results."""
    core_result = run_core_retrieval(
        driver=driver,
        gds=gds,
        task_description=task_description,
        mentioned_entities=mentioned_entities,
        ppr_config=ppr_config,
        signal_weights=signal_weights,
        relationship_types=relationship_types,
        orientation=orientation,
        apply_idf=apply_idf,
        exclude_seed_paths=exclude_seed_paths,
    )

    if not core_result:
        return []

    # Step 4: Format results into token-budgeted ContextResult items with source code.
    context_items = format_context(core_result.ppr_results, project_root, token_budget)

    logger.info(
        "Pipeline complete: %d context items (task='%s...')",
        len(context_items),
        task_description[:60],
    )
    return context_items


def ensure_graph_ready(
    driver: Driver,
    gds: GraphDataScience,
    relationship_types: list[str] | None = None,
    orientation: str = "UNDIRECTED",
    apply_idf: bool = True,
) -> Graph:
    """Apply IDF edge weights and create a fresh GDS projection.

    Args:
        driver: Active Neo4j driver.
        gds: GDS client.
        relationship_types: Edge types to include in projection (default: all four).
        orientation: GDS orientation — "UNDIRECTED", "NATURAL", or "REVERSE".
        apply_idf: When False, skip IDF weight recomputation (for ablation studies).
    """
    if apply_idf:
        logger.info("Applying IDF edge weights...")
        edge_count = apply_idf_weights(driver)
        logger.info("IDF weights applied to %d edges", edge_count)
    else:
        logger.info("Resetting edge weights to base values (apply_idf=False)...")
        edge_count = reset_base_weights(driver)
        logger.info("Base weights restored to %d edges", edge_count)

    logger.info("Refreshing GDS projection with updated weights...")
    drop_projection(gds)
    projection = project_graph(
        gds, relationship_types=relationship_types, orientation=orientation
    )

    logger.info(
        "GDS projection ready: %d nodes, %d relationships",
        projection.node_count(),
        projection.relationship_count(),
    )
    return projection
