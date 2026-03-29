"""MCP tool definitions."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from codegraph.core.graph.ppr import PPRConfig
from codegraph.core.graph.queries import (
    count_edges_by_type,
    count_nodes_by_label,
    find_dead_code,
    get_most_connected_files,
    query_entity_dependencies,
)
from codegraph.core.retrieval.pipeline import run_retrieval_pipeline
from codegraph.utils.paths import make_relative_path, make_relative_qualified_name

if TYPE_CHECKING:
    from codegraph.mcp.server import ServerState

logger = logging.getLogger(__name__)


def get_relevant_context_impl(
    task_description: str,
    mentioned_entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
    state: ServerState,
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

    total_tokens = sum(item.token_count for item in context_items)
    effective_budget = token_budget if token_budget > 0 else state.default_token_budget

    results = []
    for item in context_items:
        results.append({
            "entity_name": item.entity_name,
            "entity_type": item.entity_type,
            "qualified_name": item.qualified_name,
            "file_path": item.file_path,
            "lines": [item.line_start, item.line_end],
            "relevance_score": round(item.relevance_score, 4),
            "token_count": item.token_count,
            "source_code": item.source_code,
        })

    output = {
        "summary": {
            "result_count": len(results),
            "total_tokens": total_tokens,
            "token_budget": effective_budget,
        },
        "results": results,
    }
    return json.dumps(output, indent=2)


def query_dependencies_impl(
    entity_name: str,
    direction: str,
    depth: int,
    state: ServerState,
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

    project_root = state.project_root
    serializable = []
    for node in nodes:
        rel_file_path = make_relative_path(node.file_path, project_root)
        rel_qname = make_relative_qualified_name(node.qualified_name, node.file_path, rel_file_path)
        serializable.append({
            "qualified_name": rel_qname,
            "name": node.name,
            "label": node.label,
            "file_path": rel_file_path,
            "relationship_type": node.relationship_type,
        })
    return json.dumps(serializable, indent=2)


def find_dead_code_impl(limit: int, state: ServerState) -> str:
    """Implementation of find_dead_code tool."""
    logger.info("find_dead_code called (limit=%d)", limit)
    nodes = find_dead_code(driver=state.driver, limit=limit if limit > 0 else 50)

    project_root = state.project_root
    by_file: dict[str, list[dict]] = {}
    for node in nodes:
        rel_file_path = make_relative_path(node.file_path, project_root)
        rel_qname = make_relative_qualified_name(node.qualified_name, node.file_path, rel_file_path)
        entry = {
            "name": node.name,
            "qualified_name": rel_qname,
            "type": node.label.lower(),
            "line": node.line_number,
        }
        by_file.setdefault(rel_file_path, []).append(entry)

    output = {
        "total_count": len(nodes),
        "by_file": by_file,
    }
    return json.dumps(output, indent=2)


def get_graph_stats_impl(state: ServerState) -> str:
    """Implementation of get_graph_stats tool."""
    logger.info("get_graph_stats called")

    node_counts = count_nodes_by_label(state.driver)
    edge_counts = count_edges_by_type(state.driver)
    most_connected_raw = get_most_connected_files(state.driver, limit=10)

    project_root = state.project_root
    most_connected = [
        {
            "file_path": make_relative_path(entry["file_path"], project_root),
            "entity_count": entry["entity_count"],
        }
        for entry in most_connected_raw
    ]

    stats = {
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "total_nodes": sum(node_counts.values()),
        "total_edges": sum(edge_counts.values()),
        "most_connected_files": most_connected,
    }
    return json.dumps(stats, indent=2)


def execute_cypher_query_impl(cypher_query: str, state: ServerState) -> str:
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
