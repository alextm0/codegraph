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
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from neo4j import Driver
from graphdatascience import GraphDataScience

from codegraph.core.graph import (
    get_database_manager,
    load_full_config,
    create_gds_client,
)
from codegraph.core.graph.ppr import PPRConfig
from codegraph.core.retrieval.pipeline import ensure_graph_ready
from codegraph.mcp.prompts import LLM_SYSTEM_PROMPT
from codegraph.utils.config import parse_signal_weights
from codegraph.mcp.tools import (
    get_relevant_context_impl,
    query_dependencies_impl,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config.yaml"


def _resolve_config_path(cli_arg: str | None = None) -> Path:
    """Resolve config path from CLI arg, env var, or default location."""
    if cli_arg:
        return Path(cli_arg).resolve()
    env_path = os.environ.get("CODEGRAPH_CONFIG")
    if env_path:
        return Path(env_path).resolve()
    return _DEFAULT_CONFIG_PATH


@dataclass
class ServerState:
    """Long-lived resources initialized at startup."""

    driver: Driver
    gds: GraphDataScience
    project_root: str
    config_path: Path
    ppr_config: PPRConfig
    signal_weights: dict[str, float]
    default_token_budget: int
    default_top_k: int
    indexing_lock: threading.Lock = field(default_factory=threading.Lock)
    indexing_in_progress: bool = False


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[ServerState]:
    """Initialize Neo4j and GDS on startup."""
    logger.info("CodeGraph MCP server starting up")
    config_path = _resolve_config_path()
    logger.info("Using config: %s", config_path)

    db_manager = get_database_manager()
    db_manager.initialize(str(config_path))

    raw_config = load_full_config(config_path)

    ppr_section = raw_config.get("ppr", {})
    mcp_section = raw_config.get("mcp", {})
    seed_section = raw_config.get("seed_selection", {})

    ppr_config = PPRConfig(
        damping_factor=ppr_section.get("damping_factor", 0.70),
        max_iterations=ppr_section.get("max_iterations", 20),
        tolerance=ppr_section.get("tolerance", 1e-7),
        top_k=ppr_section.get("top_k", 30),
    )

    raw_project_root = raw_config.get("project_root", ".")
    project_root = str(config_path.parent / raw_project_root)

    if not db_manager.is_connected():
        logger.error("Cannot reach Neo4j. Shutting down.")
        sys.exit(1)

    driver = db_manager.get_driver()
    gds = create_gds_client(driver)
    try:
        ensure_graph_ready(driver, gds)
    except Exception as exc:
        logger.warning("Warm-up failed: %s", exc)

    signal_weights = parse_signal_weights(seed_section)

    state = ServerState(
        driver=driver,
        gds=gds,
        project_root=project_root,
        config_path=config_path,
        ppr_config=ppr_config,
        signal_weights=signal_weights,
        default_token_budget=mcp_section.get("default_token_budget", 6000),
        default_top_k=mcp_section.get("default_top_k", 15),
    )

    try:
        yield state
    finally:
        db_manager.close_driver()


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
) -> str:
    """Return structurally relevant source code for a task using Personalized PageRank.

    ALWAYS call this first when the user asks about code, asks you to write code, or asks
    you to refactor. Do NOT guess at file locations or function signatures — retrieve them.

    Returns a JSON object:
      summary.result_count   — number of items returned
      summary.total_tokens   — tokens consumed across all results
      results[].entity_name  — short name (e.g. "authenticate")
      results[].entity_type  — "Function", "Class", "Method", or "File"
      results[].file_path    — relative path from project root
      results[].lines        — [start, end] line numbers
      results[].relevance_score — PPR-derived rank score (higher = more relevant)
      results[].source_code  — full source text of the entity

    Parameters:
      task_description  — plain-English description of what you are trying to do
      mentioned_entities — list of exact entity names the user mentioned (e.g. ["AuthService"])
                           pass [] or null if no specific entities were named
      current_file      — relative path of the file currently open (weak seed hint); null if unknown
      top_k             — max results to return; 0 = server default (~15); raise to 20–30 for
                          broad refactors, keep at 0 for focused lookups
      token_budget      — max total tokens across all results; 0 = server default (~6000)

    Does NOT search comments, docstrings, or git history — use task_description for those signals.
    Does NOT return test files unless the task is about testing.
    """
    state = ctx.request_context.lifespan_context
    return get_relevant_context_impl(
        task_description, mentioned_entities, current_file, top_k, token_budget, state
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

    Returns a JSON array, each item:
      qualified_name    — fully qualified identifier (e.g. "src/auth.py::AuthService.login")
      name              — short name
      label             — "Function", "Class", "Method", or "File"
      file_path         — relative path from project root
      relationship_type — "CALLS", "IMPORTS", "INHERITS_FROM", or "CONTAINS"

    Parameters:
      entity_name — name or qualified_name of the entity; partial matches are accepted
      direction   — "upstream" (who calls/imports this), "downstream" (what this calls/imports),
                    or "both" (all relationships)
      depth       — 1 for direct relationships only; 2 for two-hop traversal (can be large)
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
        os.environ["CODEGRAPH_CONFIG"] = str(Path(args.config).resolve())

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("codegraph").setLevel(logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
