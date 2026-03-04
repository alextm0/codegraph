"""Graph module: Neo4j connection, creation, and querying."""

from codegraph.core.graph.connection import (
    Neo4jConfig,
    create_driver,
    verify_connectivity,
    close_driver,
    load_config,
    load_full_config,
)
from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import (
    PPRConfig,
    PPRResult,
    create_gds_client,
    project_graph,
    drop_projection,
    run_ppr,
    run_ppr_from_node_ids,
)
from codegraph.core.graph.queries import (
    NodeInfo,
    count_nodes_by_label,
    count_edges_by_type,
    get_neighbors,
    get_file_contents,
    find_callers,
    find_callees,
    find_node_by_name,
    get_inheritance_chain,
    query_entity_dependencies,
    get_most_connected_files,
)
from codegraph.core.graph.utils import normalize_path

__all__ = [
    "Neo4jConfig",
    "create_driver",
    "verify_connectivity",
    "close_driver",
    "load_config",
    "load_full_config",
    "build_graph",
    "clear_database",
    "PPRConfig",
    "PPRResult",
    "create_gds_client",
    "project_graph",
    "drop_projection",
    "run_ppr",
    "run_ppr_from_node_ids",
    "NodeInfo",
    "count_nodes_by_label",
    "count_edges_by_type",
    "get_neighbors",
    "get_file_contents",
    "find_callers",
    "find_callees",
    "find_node_by_name",
    "get_inheritance_chain",
    "query_entity_dependencies",
    "get_most_connected_files",
    "normalize_path",
]
