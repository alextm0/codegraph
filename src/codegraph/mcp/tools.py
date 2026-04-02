"""MCP tool definitions."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from codegraph.core.graph.ppr import PPRConfig
from codegraph.core.graph.queries import (
    count_edges_by_type,
    count_nodes_by_label,
    find_dead_code,
    get_most_connected_files,
    query_entity_dependencies,
    find_callers,
    find_callees,
)
from codegraph.core.retrieval.pipeline import run_retrieval_pipeline
from codegraph.core.parser.complexity import analyze_file_complexity
from codegraph.utils.paths import make_relative_path, make_relative_qualified_name

if TYPE_CHECKING:
    from codegraph.mcp.server import ServerState

logger = logging.getLogger(__name__)


def get_relevant_context_impl(
    task_description: str,
    mentioned_entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
    state: ServerState,
) -> str:
    """Implementation of get_relevant_context tool."""
    # Override PPR top_k from tool argument
    ppr_config = PPRConfig(
        damping_factor=state.ppr_config.damping_factor,
        max_iterations=state.ppr_config.max_iterations,
        tolerance=state.ppr_config.tolerance,
        top_k=top_k if top_k > 0 else state.default_top_k,
    )
    effective_budget = token_budget if token_budget > 0 else state.default_token_budget

    logger.info(
        "get_relevant_context called: task='%s...' entities=%s current_file=%s",
        task_description[:60],
        mentioned_entities,
        current_file,
    )

    context_items = run_retrieval_pipeline(
        driver=state.driver,
        gds=state.gds,
        task_description=task_description,
        project_root=state.project_root,
        mentioned_entities=mentioned_entities,
        current_file=current_file,
        ppr_config=ppr_config,
        signal_weights=state.signal_weights or None,
        token_budget=effective_budget,
    )

    total_tokens = sum(item.token_count for item in context_items)
    effective_budget = token_budget if token_budget > 0 else state.default_token_budget

    results = []
    for item in context_items:
        results.append({
            "entity_name": item.entity_name,
            "entity_type": item.entity_type,
            "qualified_name": item.qualified_name,
            "file_path": item.file_path,
            "lines": [item.line_start, item.line_end],
            "relevance_score": round(item.relevance_score, 4),
            "token_count": item.token_count,
            "source_code": item.source_code,
        })

    output = {
        "summary": {
            "result_count": len(results),
            "total_tokens": total_tokens,
            "token_budget": effective_budget,
        },
        "results": results,
    }
    return json.dumps(output, indent=2)


def query_dependencies_impl(
    entity_name: str,
    direction: str,
    depth: int,
    state: ServerState,
) -> str:
    """Implementation of query_dependencies tool."""
    logger.info(
        "query_dependencies called: entity='%s' direction=%s depth=%d",
        entity_name,
        direction,
        depth,
    )

    try:
        nodes = query_entity_dependencies(
            driver=state.driver,
            entity_name=entity_name,
            direction=direction,
            depth=depth,
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    project_root = state.project_root
    serializable = []
    for node in nodes:
        rel_file_path = make_relative_path(node.file_path, project_root)
        rel_qname = make_relative_qualified_name(node.qualified_name, node.file_path, rel_file_path)
        serializable.append({
            "qualified_name": rel_qname,
            "name": node.name,
            "label": node.label,
            "file_path": rel_file_path,
            "relationship_type": node.relationship_type,
        })
    return json.dumps(serializable, indent=2)


def find_dead_code_impl(limit: int, state: ServerState) -> str:
    """Implementation of find_dead_code tool."""
    logger.info("find_dead_code called (limit=%d)", limit)
    nodes = find_dead_code(driver=state.driver, limit=limit if limit > 0 else 50)

    project_root = state.project_root
    by_file: dict[str, list[dict]] = {}
    for node in nodes:
        rel_file_path = make_relative_path(node.file_path, project_root)
        rel_qname = make_relative_qualified_name(node.qualified_name, node.file_path, rel_file_path)
        entry = {
            "name": node.name,
            "qualified_name": rel_qname,
            "type": node.label.lower(),
            "line": node.line_number,
        }
        by_file.setdefault(rel_file_path, []).append(entry)

    output = {
        "total_count": len(nodes),
        "by_file": by_file,
    }
    return json.dumps(output, indent=2)


def get_graph_stats_impl(state: ServerState) -> str:
    """Implementation of get_graph_stats tool."""
    logger.info("get_graph_stats called")

    node_counts = count_nodes_by_label(state.driver)
    edge_counts = count_edges_by_type(state.driver)
    most_connected_raw = get_most_connected_files(state.driver, limit=10)

    project_root = state.project_root
    most_connected = [
        {
            "file_path": make_relative_path(entry["file_path"], project_root),
            "entity_count": entry["entity_count"],
        }
        for entry in most_connected_raw
    ]

    stats = {
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "total_nodes": sum(node_counts.values()),
        "total_edges": sum(edge_counts.values()),
        "most_connected_files": most_connected,
    }
    return json.dumps(stats, indent=2)


def execute_cypher_query_impl(cypher_query: str, state: ServerState) -> str:
    """Implementation of execute_cypher_query tool."""
    logger.info("execute_cypher_query called")
    try:
        def _execute(tx):
            result = tx.run(cypher_query)
            return [record.data() for record in result]

        with state.driver.session() as session:
            records = session.execute_read(_execute)
        return json.dumps(records, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def find_callers_impl(entity_name: str, state: ServerState) -> str:
    """Implementation of find_callers tool."""
    logger.info("find_callers called for '%s'", entity_name)
    results = find_callers(state.driver, entity_name)
    
    project_root = state.project_root
    serializable = []
    for res in results:
        serializable.append({
            "qualified_name": res.qualified_name,
            "name": res.name,
            "label": res.label,
            "file_path": make_relative_path(res.file_path, project_root),
        })
    return json.dumps(serializable, indent=2)


def find_callees_impl(entity_name: str, state: ServerState) -> str:
    """Implementation of find_callees tool."""
    logger.info("find_callees called for '%s'", entity_name)
    results = find_callees(state.driver, entity_name)
    
    project_root = state.project_root
    serializable = []
    for res in results:
        serializable.append({
            "qualified_name": res.qualified_name,
            "name": res.name,
            "label": res.label,
            "file_path": make_relative_path(res.file_path, project_root),
        })
    return json.dumps(serializable, indent=2)


def visualize_query_impl(task_description: str, top_k: int, state: ServerState) -> str:
    """Implementation of visualize_query tool."""
    logger.info("visualize_query called: '%s'", task_description)
    
    # We can't easily start the visualizer from here if it's not running
    # but we can return the URL and instruction.
    # In a real environment, the CLI might have started it.
    url = "http://localhost:8474"
    
    # We could potentially trigger a query in the background or just 
    # let the user know to open the browser.
    
    output = {
        "message": "Retrieval initiated. Interactive visualization available at the URL below.",
        "url": url,
        "task": task_description,
        "instructions": "Open the URL in your browser to explore the graph and retrieval results."
    }
    return json.dumps(output, indent=2)


_active_watchers: dict[str, object] = {}


def watch_directory_impl(action: str, state: ServerState) -> str:
    """Implementation of watch_directory tool."""
    import threading
    from codegraph.watcher.file_watcher import CodeGraphWatcher
    from codegraph.watcher.incremental import update_file_in_graph

    key = state.project_root

    if action == "start":
        if key in _active_watchers:
            return json.dumps({"status": "already_running", "project_root": key})

        def on_changes(paths: set[str]) -> None:
            for p in paths:
                try:
                    update_file_in_graph(state.driver, state.project_root, p)
                    logger.info("Incremental update applied: %s", p)
                except Exception as exc:
                    logger.error("Watcher update failed for %s: %s", p, exc)

        raw_config: dict = {}
        watcher = CodeGraphWatcher(state.project_root, on_changes, exclude_patterns=[])
        watcher.start()
        _active_watchers[key] = watcher

        def _poll() -> None:
            import time
            while key in _active_watchers:
                watcher.check_for_changes()
                time.sleep(0.5)

        threading.Thread(target=_poll, daemon=True, name="codegraph-watcher-poll").start()
        return json.dumps({"status": "started", "project_root": key})

    if action == "stop":
        watcher = _active_watchers.pop(key, None)
        if watcher is None:
            return json.dumps({"status": "not_running"})
        watcher.stop()  # type: ignore[attr-defined]
        return json.dumps({"status": "stopped"})

    if action == "status":
        running = key in _active_watchers
        return json.dumps({"status": "running" if running else "stopped", "project_root": key})

    return json.dumps({"error": f"Unknown action '{action}'. Use start, stop, or status."})


def analyze_complexity_impl(file_path: str, threshold: int, state: ServerState) -> str:
    """Implementation of analyze_complexity tool."""
    import os
    logger.info("analyze_complexity called for '%s' (threshold=%d)", file_path, threshold)
    
    project_root = state.project_root
    full_path = os.path.join(project_root, file_path)
    
    if not os.path.exists(full_path):
        return json.dumps({"error": f"Path not found: {file_path}"})

    files = []
    if os.path.isfile(full_path):
        if full_path.endswith('.py'):
            files.append(full_path)
    else:
        for root, _, filenames in os.walk(full_path):
            for f in filenames:
                if f.endswith('.py'):
                    files.append(os.path.join(root, f))

    all_results = []
    for f in files:
        try:
            results = analyze_file_complexity(f)
            rel_path = make_relative_path(f, project_root)
            for res in results:
                if res['complexity'] >= threshold:
                    res['file_path'] = rel_path
                    all_results.append(res)
        except Exception as e:
            logger.error("Error analyzing %s: %s", f, e)

    all_results.sort(key=lambda x: x['complexity'], reverse=True)
    return json.dumps(all_results, indent=2)
