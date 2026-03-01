"""Graph module: Neo4j connection, graph building, querying, and PPR."""

from src.graph.connection import Neo4jConfig, create_driver, verify_connectivity, close_driver
from src.graph.graph_builder import build_graph, clear_database
from src.graph.utils import normalize_path
from src.graph.queries import (
    NodeInfo,
    count_nodes_by_label,
    count_edges_by_type,
    get_neighbors,
    get_file_contents,
    find_callers,
    find_callees,
    find_node_by_name,
    get_inheritance_chain,
)
from src.graph.ppr import PPRConfig, PPRResult, create_gds_client, project_graph, drop_projection, run_ppr, run_ppr_from_node_ids

__all__ = [
    "normalize_path",
    "Neo4jConfig",
    "create_driver",
    "verify_connectivity",
    "close_driver",
    "build_graph",
    "clear_database",
    "NodeInfo",
    "count_nodes_by_label",
    "count_edges_by_type",
    "get_neighbors",
    "get_file_contents",
    "find_callers",
    "find_callees",
    "find_node_by_name",
    "get_inheritance_chain",
    "PPRConfig",
    "PPRResult",
    "create_gds_client",
    "project_graph",
    "drop_projection",
    "run_ppr",
    "run_ppr_from_node_ids",
]
