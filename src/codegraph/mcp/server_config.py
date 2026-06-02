"""MCP server configuration resolution and ServerState construction."""

from __future__ import annotations

import logging
import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

from graphdatascience import GraphDataScience
from neo4j import Driver

from codegraph.core.graph import (
    create_gds_client,
    get_database_manager,
    load_full_config,
)
from codegraph.core.graph.ppr import PPRConfig
from codegraph.core.retrieval.pipeline import ensure_graph_ready
from codegraph.utils.config import parse_signal_weights, resolve_project_root

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config.yaml"


def resolve_config_path(cli_arg: str | None = None) -> Path:
    """Resolve config path from CLI arg, env var, or default location."""
    if cli_arg:
        return Path(cli_arg).resolve()
    env_path = os.environ.get("CODEGRAPH_CONFIG")
    if env_path:
        return Path(env_path).resolve()
    return _DEFAULT_CONFIG_PATH


@dataclass(frozen=True)
class McpRuntimeSettings:
    """Parsed MCP-related settings from config.yaml."""

    config_path: Path
    project_root: str
    ppr_config: PPRConfig
    signal_weights: dict[str, float]
    default_token_budget: int
    default_top_k: int


def load_mcp_runtime_settings(config_path: Path) -> McpRuntimeSettings:
    """Load and parse MCP/PPR/seed settings from a config file."""
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

    project_root = str(resolve_project_root(raw_config, config_path))

    return McpRuntimeSettings(
        config_path=config_path,
        project_root=project_root,
        ppr_config=ppr_config,
        signal_weights=parse_signal_weights(seed_section),
        default_token_budget=mcp_section.get("default_token_budget", 6000),
        default_top_k=mcp_section.get("default_top_k", 15),
    )


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


class ServerStateFactory:
    """Build ServerState from config path with Neo4j/GDS initialization."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or resolve_config_path()

    def create(self) -> ServerState:
        """Initialize database connections and return ready ServerState."""
        logger.info("Using config: %s", self.config_path)

        db_manager = get_database_manager()
        db_manager.initialize(str(self.config_path))

        settings = load_mcp_runtime_settings(self.config_path)

        if not db_manager.is_connected():
            logger.error("Cannot reach Neo4j. Shutting down.")
            sys.exit(1)

        driver = db_manager.get_driver()
        gds = create_gds_client(driver)
        try:
            ensure_graph_ready(driver, gds)
        except Exception as exc:
            logger.warning("Warm-up failed: %s", exc)

        return ServerState(
            driver=driver,
            gds=gds,
            project_root=settings.project_root,
            config_path=settings.config_path,
            ppr_config=settings.ppr_config,
            signal_weights=settings.signal_weights,
            default_token_budget=settings.default_token_budget,
            default_top_k=settings.default_top_k,
        )

    @staticmethod
    def shutdown() -> None:
        """Close the shared database manager."""
        get_database_manager().close_driver()
