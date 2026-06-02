"""Shortest-path tracing from PPR seeds to retrieval targets."""

import logging

from neo4j import Driver

logger = logging.getLogger(__name__)


def batch_trace_paths(
    driver: Driver,
    seed_ids: list[int],
    target_ids: list[str],
    max_hops: int = 6,
) -> dict[str, dict]:
    """Find shortest paths for multiple entities in one query."""
    results: dict[str, dict] = {
        tid: {"path_str": "(no path traced)", "path_ids": []} for tid in target_ids
    }

    if not seed_ids or not target_ids:
        return results

    try:
        with driver.session() as session:
            direct_res = session.run(
                """
                MATCH (n) 
                WHERE id(n) IN $seed_ids 
                AND (n.qualified_name IN $tids OR n.file_path IN $tids)
                RETURN n.qualified_name AS qname, n.file_path AS fp
                """,
                tids=target_ids,
                seed_ids=seed_ids,
            )
            direct_matches = set()
            for r in direct_res:
                if r["qname"] in target_ids:
                    direct_matches.add(r["qname"])
                if r["fp"] in target_ids:
                    direct_matches.add(r["fp"])

            for tid in direct_matches:
                results[tid] = {"path_str": "direct seed", "path_ids": [tid]}

            targets_to_trace = [tid for tid in target_ids if tid not in direct_matches]
            if not targets_to_trace:
                return results

            query_res = session.run(
                f"""
                UNWIND $target_ids AS tid
                MATCH (seed) WHERE id(seed) IN $seed_ids
                MATCH (target) 
                WHERE (tid CONTAINS '::' AND target.qualified_name = tid)
                   OR (NOT tid CONTAINS '::' AND target.file_path = tid)
                MATCH p = shortestPath((seed)-[*..{max_hops}]-(target))
                WITH tid, p
                ORDER BY length(p) ASC
                WITH tid, head(collect(p)) AS p
                RETURN tid,
                       [node IN nodes(p) | node.qualified_name] AS path_ids,
                       [node IN nodes(p) | coalesce(node.name, node.file_path, '')] AS node_names,
                       [rel IN relationships(p) | type(rel)] AS rel_types
                """,
                target_ids=targets_to_trace,
                seed_ids=seed_ids,
            )
            for record in query_res:
                tid = record["tid"]
                results[tid] = {
                    "path_str": _format_path(record["node_names"], record["rel_types"]),
                    "path_ids": record["path_ids"],
                }
    except Exception as exc:
        logger.debug("batch_trace_paths failed: %s", exc)
        for tid in target_ids:
            if results[tid]["path_str"] == "(no path traced)":
                results[tid]["path_str"] = "(trace error)"

    return results


def trace_path_to_seed(
    driver: Driver,
    seed_ids: list[int],
    file_path: str,
    max_hops: int = 6,
) -> str:
    """Find the shortest path from any seed node to the given file in the graph.

    Returns a human-readable string like:
      "DateField -[CONTAINS]-> fields.py"
    or "(no path traced)" if unreachable within max_hops.
    If the file_path IS a seed (direct match), returns "direct seed".
    Returns "(trace error)" on any exception.
    """
    try:
        return _run_trace_query(driver, seed_ids, file_path, max_hops)
    except Exception as exc:
        logger.debug("trace_path_to_seed failed for '%s': %s", file_path, exc)
        return "(trace error)"


def trace_path_ids_to_seed(
    driver: Driver,
    seed_ids: list[int],
    file_path: str,
    max_hops: int = 6,
) -> list[str]:
    """Find the shortest path from any seed to the file and return node IDs (qualified names)."""
    try:
        with driver.session() as session:
            result = session.run(
                f"""
                MATCH (seed) WHERE id(seed) IN $seed_ids
                MATCH (target:File {{file_path: $file_path}})
                MATCH p = shortestPath((seed)-[*..{max_hops}]-(target))
                RETURN [node IN nodes(p) | node.qualified_name] AS path_ids
                ORDER BY length(p) ASC
                LIMIT 1
                """,
                seed_ids=seed_ids,
                file_path=file_path,
            ).single()

        if not result or not result["path_ids"]:
            return []
        return result["path_ids"]
    except Exception as exc:
        logger.debug("trace_path_ids_to_seed failed for '%s': %s", file_path, exc)
        return []


def _run_trace_query(
    driver: Driver,
    seed_ids: list[int],
    file_path: str,
    max_hops: int,
) -> str:
    """Execute the shortest-path Cypher and format the result."""
    with driver.session() as session:
        direct = session.run(
            "MATCH (f:File {file_path: $fp}) WHERE id(f) IN $ids RETURN count(f) AS cnt",
            fp=file_path,
            ids=seed_ids,
        ).single()
        if direct and direct["cnt"] > 0:
            return "direct seed"

        result = session.run(
            f"""
            MATCH (seed) WHERE id(seed) IN $seed_ids
            MATCH (target:File {{file_path: $file_path}})
            MATCH p = shortestPath((seed)-[*..{max_hops}]-(target))
            RETURN
                [node IN nodes(p) | coalesce(node.name, node.file_path, '')] AS node_names,
                [rel IN relationships(p) | type(rel)] AS rel_types,
                length(p) AS path_length
            ORDER BY path_length ASC
            LIMIT 1
            """,
            seed_ids=seed_ids,
            file_path=file_path,
        ).single()

    if not result:
        return "(no path traced)"

    return _format_path(result["node_names"], result["rel_types"])


def shortest_path_between(
    driver: Driver,
    source_qname: str,
    target_qname: str,
    max_hops: int = 12,
) -> dict[str, object]:
    """Return the shortest undirected path between two entities by qualified_name."""
    empty: dict[str, object] = {"linked": False, "path_ids": [], "hops": 0}
    if not source_qname or not target_qname or source_qname == target_qname:
        if source_qname == target_qname and source_qname:
            return {"linked": True, "path_ids": [source_qname], "hops": 0}
        return empty

    try:
        with driver.session() as session:
            record = session.run(
                f"""
                MATCH (a {{qualified_name: $source}}), (b {{qualified_name: $target}})
                MATCH p = shortestPath((a)-[*..{max_hops}]-(b))
                RETURN [node IN nodes(p) | node.qualified_name] AS path_ids
                LIMIT 1
                """,
                source=source_qname,
                target=target_qname,
            ).single()
            if not record:
                return empty
            path_ids: list[str] = record["path_ids"] or []
            hops = max(0, len(path_ids) - 1)
            return {"linked": True, "path_ids": path_ids, "hops": hops}
    except Exception as exc:
        logger.debug("shortest_path_between failed: %s", exc)
        return empty


def _format_path(node_names: list[str], rel_types: list[str]) -> str:
    """Interleave node names and relationship types into a readable path string."""
    _MAX_NODE_LEN = 30
    parts: list[str] = []
    for i, name in enumerate(node_names):
        truncated = name[:_MAX_NODE_LEN] if len(name) > _MAX_NODE_LEN else name
        parts.append(truncated)
        if i < len(rel_types):
            parts.append(f"-[{rel_types[i]}]->")
    return " ".join(parts)
