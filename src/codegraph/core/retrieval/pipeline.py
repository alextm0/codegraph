"""Retrieval pipeline orchestration."""

import logging
from graphdatascience import GraphDataScience
from graphdatascience.graph.graph_object import Graph
from neo4j import Driver

from codegraph.core.graph.ppr import PPRConfig, drop_projection, project_graph, run_ppr_from_node_ids
from codegraph.core.retrieval.post_processing import ContextResult, apply_idf_weights, format_context
from codegraph.core.retrieval.seed_selection import PersonalizationVector, extract_entity_names, extract_seeds

logger = logging.getLogger(__name__)


def run_retrieval_pipeline(
    driver: Driver,
    gds: GraphDataScience,
    task_description: str,
    project_root: str,
    mentioned_entities: list[str] | None = None,
    current_file: str | None = None,
    ppr_config: PPRConfig | None = None,
    signal_weights: dict[str, float] | None = None,
    token_budget: int = 6000,
    relationship_types: list[str] | None = None,
    orientation: str = "UNDIRECTED",
    apply_idf: bool = True,
) -> list[ContextResult]:
    """Run the full retrieval pipeline and return context results."""
    if ppr_config is None:
        ppr_config = PPRConfig()

    # Auto-augment mentioned_entities with identifiers extracted from the task text.
    auto_entities = extract_entity_names(task_description)
    existing = set(mentioned_entities or [])
    augmented_entities = list(mentioned_entities or []) + [
        e for e in auto_entities if e not in existing
    ]

    # Step 1: Extract seeds from the task description.
    seeds = extract_seeds(
        driver,
        task_description=task_description,
        mentioned_entities=augmented_entities or None,
        current_file=current_file,
        signal_weights=signal_weights,
    )
    if not seeds.seeds:
        logger.warning("Pipeline: no seeds found — returning empty context")
        return []

    # Step 2: Prepare the graph for PPR (IDF weights + fresh GDS projection).
    ensure_graph_ready(
        driver,
        gds,
        relationship_types=relationship_types,
        orientation=orientation,
        apply_idf=apply_idf,
    )

    # Step 3: Run Personalized PageRank using weighted seed dict (preserves signal weights).
    ppr_results = run_ppr_from_node_ids(gds, driver, seeds.seeds, ppr_config)
    if not ppr_results:
        logger.warning("Pipeline: PPR returned no results")
        return []

    # Step 4: Format results into token-budgeted ContextResult items with source code.
    context_items = format_context(ppr_results, project_root, token_budget)

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

    logger.info("Refreshing GDS projection with updated weights...")
    drop_projection(gds)
    projection = project_graph(gds, relationship_types=relationship_types, orientation=orientation)

    logger.info(
        "GDS projection ready: %d nodes, %d relationships",
        projection.node_count(),
        projection.relationship_count(),
    )
    return projection
