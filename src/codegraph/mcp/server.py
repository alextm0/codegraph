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
    ctx: Context,
    include_explanations: bool = True,
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
      include_explanations — default true; attach seed provenance and reasoning paths per result
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
    mode: str = "dependencies",
) -> str:
    """Return structural relationships for a code entity (dependencies, search, hierarchy).

    Modes:
    - mode="dependencies" (default): CALLS/IMPORTS neighbors; use direction and depth.
    - mode="symbol_search": fast substring search; entity_name is the pattern; depth ignored.
    - mode="class_hierarchy": INHERITS_FROM ancestors/subclasses; direction upstream/downstream/both.

    Use symbol_search or class_hierarchy when you know the symbol name and want a cheap lookup
    instead of running full PPR via get_relevant_context.

    CRITICAL USAGE HINTS:
    - dependencies: depth=1 direct, depth=2 transitive
    - class_hierarchy: upstream=parents, downstream=subclasses
    - If the graph is empty, this tool will auto-trigger a rebuild and ask you to wait.

    Returns a JSON object:
      mode, result_count, results[] (qualified_name, name, label, file_path, relationship_type)

    Parameters:
      entity_name — name, qualified_name, or search pattern (symbol_search mode)
      direction   — "upstream", "downstream", or "both"
      depth       — 1 or 2 (dependencies mode only)
      mode        — "dependencies", "symbol_search", or "class_hierarchy"
    """
    state = ctx.request_context.lifespan_context
    return query_dependencies_impl(entity_name, direction, depth, state, mode=mode)


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
