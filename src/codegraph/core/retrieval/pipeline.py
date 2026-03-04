"""Retrieval pipeline orchestration."""

import logging
from graphdatascience import GraphDataScience
from graphdatascience.graph.graph_object import Graph
from neo4j import Driver

from codegraph.core.graph.ppr import PPRConfig, drop_projection, project_graph, run_ppr_from_node_ids
from codegraph.core.retrieval.post_processing import ContextResult, apply_idf_weights, format_context
from codegraph.core.retrieval.seed_selection import PersonalizationVector, extract_seeds

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
) -> list[ContextResult]:
    """Run the full retrieval pipeline and return context results."""
    if ppr_config is None:
        ppr_config = PPRConfig()

    # Step 1: Extract seeds from the task description.
    seeds = extract_seeds(
        driver,
        task_description=task_description,
        mentioned_entities=mentioned_entities,
        current_file=current_file,
        signal_weights=signal_weights,
    )
    if not seeds.seeds:
        logger.warning("Pipeline: no seeds found — returning empty context")
        return []

    # Step 2: Prepare the graph for PPR (IDF weights + fresh GDS projection).
    ensure_graph_ready(driver, gds)

    # Step 3: Run Personalized PageRank from the seed node IDs.
    seed_node_ids = list(seeds.seeds.keys())
    ppr_results = run_ppr_from_node_ids(gds, driver, seed_node_ids, ppr_config)
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


def ensure_graph_ready(driver: Driver, gds: GraphDataScience) -> Graph:
    """Apply IDF edge weights and create a fresh GDS projection."""
    logger.info("Applying IDF edge weights...")
    edge_count = apply_idf_weights(driver)
    logger.info("IDF weights applied to %d edges", edge_count)

    logger.info("Refreshing GDS projection with updated weights...")
    drop_projection(gds)
    projection = project_graph(gds)

    logger.info(
        "GDS projection ready: %d nodes, %d relationships",
        projection.node_count(),
        projection.relationship_count(),
    )
    return projection
