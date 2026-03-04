"""MCP tool definitions."""

import dataclasses
import json
import logging
from mcp.server.fastmcp import Context

from codegraph.core.graph.ppr import PPRConfig, run_ppr_from_node_ids
from codegraph.core.graph.queries import (
    count_edges_by_type,
    count_nodes_by_label,
    find_dead_code,
    get_most_connected_files,
    query_entity_dependencies,
)
from codegraph.core.retrieval.pipeline import run_retrieval_pipeline

logger = logging.getLogger(__name__)

def get_relevant_context_impl(
    task_description: str,
    mentioned_entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
    state,
) -> str:
    """Implementation of get_relevant_context tool."""
    # Override PPR top_k from tool argument
    ppr_config = PPRConfig(
        damping_factor=state.ppr_config.damping_factor,
        max_iterations=state.ppr_config.max_iterations,
        tolerance=state.ppr_config.tolerance,
        top_k=top_k if top_k > 0 else state.default_top_k,
    )
    effective_budget = token_budget if token_budget > 0 else state.default_token_budget

    logger.info(
        "get_relevant_context called: task='%s...' entities=%s current_file=%s",
        task_description[:60],
        mentioned_entities,
        current_file,
    )

    context_items = run_retrieval_pipeline(
        driver=state.driver,
        gds=state.gds,
        task_description=task_description,
        project_root=state.project_root,
        mentioned_entities=mentioned_entities,
        current_file=current_file,
        ppr_config=ppr_config,
        signal_weights=state.signal_weights or None,
        token_budget=effective_budget,
    )

    # Serialize each ContextResult dataclass to a plain dict for JSON output.
    serializable = [dataclasses.asdict(item) for item in context_items]
    return json.dumps(serializable, indent=2)

def query_dependencies_impl(
    entity_name: str,
    direction: str,
    depth: int,
    state,
) -> str:
    """Implementation of query_dependencies tool."""
    logger.info(
        "query_dependencies called: entity='%s' direction=%s depth=%d",
        entity_name,
        direction,
        depth,
    )

    try:
        nodes = query_entity_dependencies(
            driver=state.driver,
            entity_name=entity_name,
            direction=direction,
            depth=depth,
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    serializable = [
        {
            "qualified_name": node.qualified_name,
            "name": node.name,
            "label": node.label,
            "file_path": node.file_path,
        }
        for node in nodes
    ]
    return json.dumps(serializable, indent=2)

def find_dead_code_impl(limit: int, state) -> str:
    """Implementation of find_dead_code tool."""
    logger.info("find_dead_code called (limit=%d)", limit)
    nodes = find_dead_code(driver=state.driver, limit=limit if limit > 0 else 50)
    serializable = [
        {
            "qualified_name": node.qualified_name,
            "name": node.name,
            "label": node.label,
            "file_path": node.file_path,
        }
        for node in nodes
    ]
    return json.dumps(serializable, indent=2)


def get_graph_stats_impl(state) -> str:
    """Implementation of get_graph_stats tool."""
    logger.info("get_graph_stats called")

    node_counts = count_nodes_by_label(state.driver)
    edge_counts = count_edges_by_type(state.driver)
    most_connected = get_most_connected_files(state.driver, limit=10)

    stats = {
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "total_nodes": sum(node_counts.values()),
        "total_edges": sum(edge_counts.values()),
        "most_connected_files": most_connected,
    }
    return json.dumps(stats, indent=2)

def execute_cypher_query_impl(cypher_query: str, state) -> str:
    """Implementation of execute_cypher_query tool."""
    logger.info("execute_cypher_query called")
    try:
        def _execute(tx):
            result = tx.run(cypher_query)
            return [record.data() for record in result]
            
        with state.driver.session() as session:
            records = session.execute_read(_execute)
        return json.dumps(records, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
