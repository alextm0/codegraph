"""FastMCP server instance and lifecycle management."""

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from codegraph.core.graph import (
    Neo4jConfig,
    close_driver,
    create_driver,
    load_full_config,
    verify_connectivity,
)
from codegraph.core.graph.ppr import PPRConfig, create_gds_client
from codegraph.core.retrieval.pipeline import ensure_graph_ready
from codegraph.mcp.tools import (
    get_relevant_context_impl,
    query_dependencies_impl,
    get_graph_stats_impl,
)

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config.yaml"

@dataclass
class ServerState:
    """Long-lived resources initialized at startup."""
    driver: object
    gds: object
    project_root: str
    ppr_config: PPRConfig
    default_token_budget: int
    default_top_k: int

@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[ServerState]:
    """Initialize Neo4j and GDS on startup."""
    logger.info("CodeGraph MCP server starting up")
    raw_config = load_full_config(_CONFIG_PATH)

    neo4j_section = raw_config.get("neo4j", {})
    ppr_section = raw_config.get("ppr", {})
    mcp_section = raw_config.get("mcp", {})

    neo4j_config = Neo4jConfig(
        uri=neo4j_section.get("uri", "neo4j://localhost:7687"),
        username=neo4j_section.get("username", "neo4j"),
        password=neo4j_section.get("password", ""),
        database=neo4j_section.get("database", "neo4j"),
    )
    ppr_config = PPRConfig(
        damping_factor=ppr_section.get("damping_factor", 0.85),
        max_iterations=ppr_section.get("max_iterations", 20),
        tolerance=ppr_section.get("tolerance", 1e-7),
        top_k=ppr_section.get("top_k", 20),
    )

    raw_project_root = raw_config.get("project_root", ".")
    project_root = str(Path(_CONFIG_PATH).parent / raw_project_root)

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

    state = ServerState(
        driver=driver,
        gds=gds,
        project_root=project_root,
        ppr_config=ppr_config,
        default_token_budget=mcp_section.get("default_token_budget", 6000),
        default_top_k=mcp_section.get("default_top_k", 15),
    )

    try:
        yield state
    finally:
        close_driver(driver)

mcp = FastMCP(
    name="codegraph",
    instructions="Graph-based code context retrieval.",
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

def main():
    """Start the MCP server using STDIO transport."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    mcp.run()

if __name__ == "__main__":
    main()
