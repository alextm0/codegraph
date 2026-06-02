"""FastMCP server instance and lifecycle management.

Design notes:
- The lifespan pattern (@asynccontextmanager) ensures the Neo4j driver and GDS client are
  properly closed on shutdown even if a tool call raises.
- ServerState is injected into every tool call via FastMCP's context dependency mechanism;
  tools never access global state directly.
- Transport is STDIO by default (standard for local MCP servers with Claude Desktop/Code).
"""

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from codegraph.mcp.prompts import LLM_SYSTEM_PROMPT
from codegraph.mcp.server_config import (
    ServerState,
    ServerStateFactory,
    resolve_config_path,
)

# Re-export for callers that import ServerState from server.py
__all__ = ["ServerState", "ServerStateFactory", "resolve_config_path", "mcp", "main"]
from codegraph.mcp.tools import (
    get_relevant_context_impl,
    query_dependencies_impl,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[ServerState]:
    """Initialize Neo4j and GDS on startup."""
    logger.info("CodeGraph MCP server starting up")
    factory = ServerStateFactory()
    state = factory.create()
    try:
        yield state
    finally:
        ServerStateFactory.shutdown()


mcp = FastMCP(
    name="codegraph",
    instructions=LLM_SYSTEM_PROMPT,
    lifespan=_lifespan,
)


@mcp.tool(annotations={"readOnlyHint": True, "idempotentHint": True})
def get_relevant_context(
    task_description: str,
    mentioned_entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
    include_explanations: bool,
    ctx: Context,
) -> str:
    """Return structurally relevant source code for a task using Personalized PageRank.

    ALWAYS call this first when the user asks about code, asks you to write code, or asks
    you to refactor. Do NOT guess at file locations or function signatures — retrieve them.

    CRITICAL USAGE HINTS:
    - Use the returned 'file_path' and 'lines' to read the source code or make modifications.
    - Results are ranked by structural relevance. Trust the top-ranked files.
    - If the graph is empty, this tool will auto-trigger a rebuild and ask you to wait. Wait 15-30s and retry.

    Returns a JSON object:
      summary.result_count    — number of items returned
      summary.total_tokens    — tokens consumed across all results
      summary.token_budget    — budget applied
      summary.visualizer_url  — link to the graph visualizer
      results[].entity_name   — short name (e.g. "authenticate")
      results[].entity_type   — "Function", "Class", "Method", or "File"
      results[].qualified_name  — file_path::name identity
      results[].file_path     — relative path from project root
      results[].lines         — [start, end] line numbers
      results[].relevance_score — PPR rank score (higher = more relevant)
      results[].token_count   — tokens in source_code
      results[].source_code   — full source text of the entity
      results[].explanation   — (optional) seed path and contribution when include_explanations=true
      seeds[]                 — (optional) seed nodes when include_explanations=true

    Parameters:
      task_description     — plain-English description of what you are trying to do
      mentioned_entities   — entity names mentioned (e.g. ["AuthService"]); null if none
      current_file         — deprecated compatibility field; ignored by retrieval
      top_k                — max results; 0 = server default (~30)
      token_budget         — max total tokens; 0 = server default (~6000)
      include_explanations — when true, attach seed provenance and reasoning paths per result
    """
    state = ctx.request_context.lifespan_context
    return get_relevant_context_impl(
        task_description,
        mentioned_entities,
        current_file,
        top_k,
        token_budget,
        state,
        include_explanations=include_explanations,
    )


@mcp.tool(annotations={"readOnlyHint": True, "idempotentHint": True})
def query_dependencies(
    entity_name: str,
    direction: str,
    depth: int,
    ctx: Context,
) -> str:
    """Return callers, callees, and imports for a specific code entity.

    Use this AFTER get_relevant_context when you need to understand:
    - Who calls a function before you change its signature (direction="upstream")
    - What a function calls internally (direction="downstream")
    - The full dependency fan in both directions (direction="both")

    Do NOT use this as the first tool — you need to confirm entity names exist first
    via get_relevant_context.

    CRITICAL USAGE HINTS:
    - Use 'depth=1' for direct dependencies, or 'depth=2' to see transitive dependencies.
    - If the graph is empty, this tool will auto-trigger a rebuild and ask you to wait.

    Returns a JSON object:
      result_count — number of related entities returned
      results[]    — each item has:
        qualified_name, name, label, file_path, relationship_type

    Parameters:
      entity_name — exact name or qualified_name (use get_relevant_context to confirm)
      direction   — "upstream", "downstream", or "both"
      depth       — 1 for direct neighbors; 2 for two-hop (can be large)
    """
    state = ctx.request_context.lifespan_context
    return query_dependencies_impl(entity_name, direction, depth, state)


def main() -> None:
    """Start the MCP server using STDIO transport.

    Accepts an optional --config argument pointing to a config.yaml file.
    The CODEGRAPH_CONFIG environment variable is also respected as a fallback.
    """
    import argparse

    parser = argparse.ArgumentParser(description="CodeGraph MCP server")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args, _ = parser.parse_known_args()

    if args.config:
        os.environ["CODEGRAPH_CONFIG"] = str(resolve_config_path(args.config))

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("codegraph").setLevel(logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
