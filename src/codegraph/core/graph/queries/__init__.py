"""Cypher query functions for the code graph.

Design notes:
- Most functions are read-only (MATCH only). Exception: delete_file_entities runs DETACH DELETE
  and requires a writable driver; callers should obtain one from DatabaseManager.
- driver defaults to None; pass one explicitly in tests or accept the singleton from DatabaseManager.
- To add a new node label: update any label-filtering queries (e.g. find_dead_code, count_nodes_by_label)
  to include the new label, and add a corresponding result dataclass if needed.
"""

from codegraph.core.graph.queries.dependencies import (
    _both_directions_cypher,
    _downstream_cypher,
    _row_to_node_info,
    _row_to_node_info_with_rel,
    _upstream_cypher,
    _validate_direction,
    find_callees,
    find_callers,
    find_node_by_name,
    find_node_by_pattern,
    get_inheritance_chain,
    get_neighbors,
    query_entity_dependencies,
)
from codegraph.core.graph.queries.models import DeadCodeNode, NodeInfo, NodeInfoWithRel
from codegraph.core.graph.queries.path_tracing import (
    _format_path,
    _run_trace_query,
    batch_trace_paths,
    shortest_path_between,
    trace_path_ids_to_seed,
    trace_path_to_seed,
)
from codegraph.core.graph.queries.stats import (
    count_edges_by_type,
    count_nodes_by_label,
    find_dead_code,
    get_most_connected_files,
)
from codegraph.core.graph.queries.subgraph import (
    delete_file_entities,
    expand_qnames_with_file_nodes,
    get_file_contents,
    get_full_graph,
    get_node_detail,
    get_subgraph_by_prefix,
    get_subgraph_for_nodes,
)

__all__ = [
    "DeadCodeNode",
    "NodeInfo",
    "NodeInfoWithRel",
    "batch_trace_paths",
    "shortest_path_between",
    "count_edges_by_type",
    "count_nodes_by_label",
    "delete_file_entities",
    "find_callees",
    "find_callers",
    "find_dead_code",
    "find_node_by_name",
    "find_node_by_pattern",
    "get_file_contents",
    "get_full_graph",
    "get_inheritance_chain",
    "get_most_connected_files",
    "get_neighbors",
    "get_node_detail",
    "expand_qnames_with_file_nodes",
    "get_subgraph_by_prefix",
    "get_subgraph_for_nodes",
    "query_entity_dependencies",
    "trace_path_ids_to_seed",
    "trace_path_to_seed",
    "_both_directions_cypher",
    "_downstream_cypher",
    "_format_path",
    "_row_to_node_info",
    "_row_to_node_info_with_rel",
    "_run_trace_query",
    "_upstream_cypher",
    "_validate_direction",
]
