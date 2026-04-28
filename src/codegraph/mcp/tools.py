"""MCP tool implementations.

Design notes:
- Thin wrappers only: each tool validates inputs and delegates immediately to core modules.
  No business logic lives here — that belongs in core/graph/ and core/retrieval/.
- ServerState (driver, gds, config) is retrieved from FastMCP context; never accessed globally.
- To add a new MCP tool: implement *_impl() here, then register it with @mcp.tool() in server.py.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from codegraph.core.graph.ppr import PPRConfig
from codegraph.core.graph.queries import query_entity_dependencies
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
    effective_top_k = top_k if top_k > 0 else state.default_top_k
    effective_budget = token_budget if token_budget > 0 else state.default_token_budget

    ppr_config = PPRConfig(
        damping_factor=state.ppr_config.damping_factor,
        max_iterations=state.ppr_config.max_iterations,
        tolerance=state.ppr_config.tolerance,
        top_k=effective_top_k,
    )

    logger.info(
        "get_relevant_context called: task='%s...' entities=%s current_file=%s top_k=%d budget=%d",
        task_description[:60],
        mentioned_entities,
        current_file,
        effective_top_k,
        effective_budget,
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

    if not context_items:
        return json.dumps({
            "summary": {"result_count": 0, "total_tokens": 0, "token_budget": effective_budget},
            "results": [],
            "hint": "No results found. Is the graph indexed? Run: codegraph rebuild",
        })

    total_tokens = sum(item.token_count for item in context_items)

    results = [
        {
            "entity_name": item.entity_name,
            "entity_type": item.entity_type,
            "qualified_name": item.qualified_name,
            "file_path": item.file_path,
            "lines": [item.line_start, item.line_end],
            "relevance_score": round(item.relevance_score, 4),
            "token_count": item.token_count,
            "source_code": item.source_code,
        }
        for item in context_items
    ]

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
        return json.dumps({
            "error": str(exc),
            "hint": "Entity not found. Use get_relevant_context first to confirm the entity name exists.",
        })

    if not nodes:
        return json.dumps({
            "result_count": 0,
            "results": [],
            "hint": f"No {direction} dependencies found for '{entity_name}'. Try direction='both' or depth=2.",
        })

    project_root = state.project_root
    serializable = [
        {
            "qualified_name": make_relative_qualified_name(
                node.qualified_name, node.file_path,
                make_relative_path(node.file_path, project_root),
            ),
            "name": node.name,
            "label": node.label,
            "file_path": make_relative_path(node.file_path, project_root),
            "relationship_type": node.relationship_type,
        }
        for node in nodes
    ]

    return json.dumps({
        "result_count": len(serializable),
        "results": serializable,
    }, indent=2)
