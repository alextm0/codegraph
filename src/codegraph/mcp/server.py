"""FastMCP server instance and lifecycle management."""

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from neo4j import Driver
from graphdatascience import GraphDataScience

from codegraph.core.graph import (
    Neo4jConfig,
    close_driver,
    create_driver,
    load_full_config,
    verify_connectivity,
)
from codegraph.core.graph.ppr import PPRConfig, create_gds_client
from codegraph.core.retrieval.pipeline import ensure_graph_ready
from codegraph.mcp.prompts import LLM_SYSTEM_PROMPT
from codegraph.mcp.tools import (
    find_dead_code_impl,
    get_graph_stats_impl,
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
    ppr_config: PPRConfig
    signal_weights: dict[str, float]
    default_token_budget: int
    default_top_k: int

@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[ServerState]:
    """Initialize Neo4j and GDS on startup."""
    logger.info("CodeGraph MCP server starting up")
    config_path = _resolve_config_path()
    logger.info("Using config: %s", config_path)
    raw_config = load_full_config(config_path)

    neo4j_section = raw_config.get("neo4j", {})
    ppr_section = raw_config.get("ppr", {})
    mcp_section = raw_config.get("mcp", {})
    seed_section = raw_config.get("seed_selection", {})

    # Read password, ensuring it is provided
    password = os.environ.get("NEO4J_PASSWORD", neo4j_section.get("password"))
    if not password:
        logger.error("Missing mandatory Neo4j configuration: NEO4J_PASSWORD must be set in environment or config.yaml")
        sys.exit(1)

    neo4j_config = Neo4jConfig(
        uri=os.environ.get("NEO4J_URI", neo4j_section.get("uri", "neo4j://localhost:7687")),
        username=os.environ.get("NEO4J_USERNAME", neo4j_section.get("username", "neo4j")),
        password=password,
        database=os.environ.get("NEO4J_DATABASE", neo4j_section.get("database", "neo4j")),
    )
    ppr_config = PPRConfig(
        damping_factor=ppr_section.get("damping_factor", 0.85),
        max_iterations=ppr_section.get("max_iterations", 20),
        tolerance=ppr_section.get("tolerance", 1e-7),
        top_k=ppr_section.get("top_k", 20),
    )

    raw_project_root = raw_config.get("project_root", ".")
    project_root = str(config_path.parent / raw_project_root)

    driver = create_driver(neo4j_config)
    if not verify_connectivity(driver):
        logger.error("Cannot reach Neo4j. Shutting down.")
        close_driver(driver)
        sys.exit(1)

    gds = create_gds_client(driver)
    try:
        ensure_graph_ready(driver, gds)
    except Exception as exc:
        logger.warning("Warm-up failed: %s", exc)

    signal_weights: dict[str, float] = {}
    if seed_section.get("entity_match_weight") is not None:
        signal_weights["entity_match"] = float(seed_section["entity_match_weight"])
    if seed_section.get("bm25_weight") is not None:
        signal_weights["bm25"] = float(seed_section["bm25_weight"])
    if seed_section.get("current_file_weight") is not None:
        signal_weights["current_file"] = float(seed_section["current_file_weight"])
    if seed_section.get("bm25_top_n") is not None:
        signal_weights["bm25_top_n"] = int(seed_section["bm25_top_n"])

    state = ServerState(
        driver=driver,
        gds=gds,
        project_root=project_root,
        ppr_config=ppr_config,
        signal_weights=signal_weights,
        default_token_budget=mcp_section.get("default_token_budget", 6000),
        default_top_k=mcp_section.get("default_top_k", 15),
    )

    try:
        yield state
    finally:
        close_driver(driver)

mcp = FastMCP(
    name="codegraph",
    instructions=LLM_SYSTEM_PROMPT,
    lifespan=_lifespan,
)

@mcp.tool()
def get_relevant_context(
    task_description: str,
    mentioned_entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
    ctx: Context,
) -> str:
    """Find structurally relevant code for a task using graph-based ranking."""
    state = ctx.request_context.lifespan_context
    return get_relevant_context_impl(
        task_description, mentioned_entities, current_file, top_k, token_budget, state
    )

@mcp.tool()
def query_dependencies(
    entity_name: str,
    direction: str,
    depth: int,
    ctx: Context,
) -> str:
    """Get dependency relationships for a specific code entity."""
    state = ctx.request_context.lifespan_context
    return query_dependencies_impl(entity_name, direction, depth, state)

@mcp.tool()
def get_graph_stats(ctx: Context) -> str:
    """Return statistics about the code dependency graph."""
    state = ctx.request_context.lifespan_context
    return get_graph_stats_impl(state)


@mcp.tool()
def find_dead_code(limit: int, ctx: Context) -> str:
    """Find functions and methods that are never called by other code in the graph.

    Returns candidates for dead code (zero incoming CALLS edges). Note: this may
    include public API entry points, route handlers, and test functions.
    """
    state = ctx.request_context.lifespan_context
    return find_dead_code_impl(limit, state)

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
        level=logging.INFO,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    mcp.run()

if __name__ == "__main__":
    main()
