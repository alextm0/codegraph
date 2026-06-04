"""MCP tool implementations.

Design notes:
- Thin wrappers only: each tool validates inputs and delegates immediately to core modules.
  No business logic lives here — that belongs in core/graph/ and core/retrieval/.
- ServerState (driver, gds, config) is retrieved from FastMCP context; never accessed globally.
- To add a new MCP tool: implement *_impl() here, then register it with @mcp.tool() in server.py.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING

from codegraph.core.graph.ppr import PPRConfig
from codegraph.core.graph.queries import (
    count_nodes_by_label,
    query_class_hierarchy,
    query_entity_dependencies,
    search_symbols,
)
from codegraph.core.retrieval.pipeline import run_core_retrieval
from codegraph.core.retrieval.post_processing import format_context
from codegraph.utils.paths import (
    graph_file_path_scope,
    make_relative_path,
    make_relative_qualified_name,
)

if TYPE_CHECKING:
    from codegraph.mcp.server import ServerState

logger = logging.getLogger(__name__)


def _empty_graph_payload() -> dict[str, str]:
    """Standard JSON payload when the graph has no indexed nodes."""
    return {
        "error": "Graph index is empty — indexing is now running in the background.",
        "action": "Wait for indexing to complete, then retry this tool.",
        "hint": "Indexing typically takes 10–60 seconds. Check progress with: codegraph status",
    }


def _graph_is_empty(state: ServerState) -> bool:
    """Return True if the Neo4j graph has no indexed nodes."""
    try:
        counts = count_nodes_by_label(state.driver)
        return sum(counts.values()) == 0
    except Exception as exc:
        logger.warning(
            "Could not verify graph population (%s); assuming graph is not empty",
            exc,
        )
        return False


def _start_background_index(state: ServerState) -> None:
    """Spawn a background thread to index the project if one is not already running."""
    with state.indexing_lock:
        if state.indexing_in_progress:
            return
        state.indexing_in_progress = True

    def _index() -> None:
        try:
            logger.info(
                "Auto-index: starting background indexing of %s", state.project_root
            )
            from codegraph.utils.ignore import load_ignore_patterns
            from codegraph.utils.config import load_raw_config
            from codegraph.core.graph import clear_database, build_graph
            from codegraph.core.parser import create_parser, parse_directory

            raw_config = load_raw_config(state.config_path)
            exclude = raw_config.get("parser", {}).get("exclude_patterns", [])
            exclude += raw_config.get("exclude_patterns", [])

            from pathlib import Path

            ignore_file = Path(state.project_root) / ".cgignore"
            if ignore_file.exists():
                exclude.extend(load_ignore_patterns(ignore_file))

            parser = create_parser()
            all_entities = parse_directory(
                state.project_root, parser, exclude_patterns=exclude
            )
            clear_database(state.driver)
            counts = build_graph(state.driver, all_entities)
            total = sum(
                v
                for k, v in counts.items()
                if k in ("File", "Function", "Class", "Method")
            )
            logger.info("Auto-index: complete — %d nodes indexed", total)
        except Exception:
            logger.exception("Auto-index: background indexing failed")
        finally:
            with state.indexing_lock:
                state.indexing_in_progress = False

    thread = threading.Thread(target=_index, daemon=True, name="codegraph-auto-index")
    thread.start()


def get_relevant_context_impl(
    task_description: str,
    mentioned_entities: list[str] | None,
    current_file: str | None,
    top_k: int,
    token_budget: int,
    state: ServerState,
    include_explanations: bool | None = None,
) -> str:
    """Implementation of get_relevant_context tool."""
    # Kept in the MCP signature for compatibility; active-file seeding is deprecated.
    _ = current_file
    if include_explanations is None:
        include_explanations = state.default_include_explanations
    effective_top_k = top_k if top_k > 0 else state.default_top_k
    effective_budget = token_budget if token_budget > 0 else state.default_token_budget

    ppr_config = PPRConfig(
        damping_factor=state.ppr_config.damping_factor,
        max_iterations=state.ppr_config.max_iterations,
        tolerance=state.ppr_config.tolerance,
        top_k=effective_top_k,
    )

    logger.info(
        "get_relevant_context called: task='%s...' entities=%s top_k=%d budget=%d",
        task_description[:60],
        mentioned_entities,
        effective_top_k,
        effective_budget,
    )

    if _graph_is_empty(state):
        logger.warning("get_relevant_context: graph is empty — triggering auto-index")
        _start_background_index(state)
        return json.dumps(_empty_graph_payload())

    try:
        from codegraph.core.retrieval.explanations import (
            build_explained_results,
            explained_result_to_dict,
        )

        core_result = run_core_retrieval(
            driver=state.driver,
            gds=state.gds,
            task_description=task_description,
            mentioned_entities=mentioned_entities,
            ppr_config=ppr_config,
            signal_weights=state.signal_weights or None,
            exclude_seed_paths=state.exclude_seed_paths or None,
        )
        if not core_result:
            return json.dumps(
                {
                    "summary": {
                        "result_count": 0,
                        "total_tokens": 0,
                        "token_budget": effective_budget,
                    },
                    "results": [],
                    "hint": "No results found. Is the graph indexed? Run: codegraph rebuild",
                }
            )

        explanation_by_qname: dict = {}
        if include_explanations:
            explained = build_explained_results(
                state.driver, core_result, top_k=effective_top_k
            )
            explanation_by_qname = {e.qualified_name: e for e in explained}

        context_items = format_context(
            core_result.ppr_results, state.project_root, effective_budget
        )
    except Exception as exc:
        logger.exception("get_relevant_context pipeline failed")
        return json.dumps(
            {
                "error": "Retrieval pipeline failed",
                "detail": str(exc),
                "hint": "Run 'codegraph doctor' to check system health, or 'codegraph rebuild' to re-index.",
            }
        )

    if not context_items:
        return json.dumps(
            {
                "summary": {
                    "result_count": 0,
                    "total_tokens": 0,
                    "token_budget": effective_budget,
                },
                "results": [],
                "hint": "No results found. Is the graph indexed? Run: codegraph rebuild",
            }
        )

    total_tokens = sum(item.token_count for item in context_items)

    results = []
    for item in context_items:
        row = {
            "entity_name": item.entity_name,
            "entity_type": item.entity_type,
            "qualified_name": item.qualified_name,
            "file_path": item.file_path,
            "lines": [item.line_start, item.line_end],
            "relevance_score": round(item.relevance_score, 4),
            "token_count": item.token_count,
            "source_code": item.source_code,
        }
        if include_explanations and item.qualified_name in explanation_by_qname:
            row["explanation"] = explained_result_to_dict(
                explanation_by_qname[item.qualified_name]
            )
        results.append(row)

    output: dict = {
        "summary": {
            "result_count": len(results),
            "total_tokens": total_tokens,
            "token_budget": effective_budget,
            "visualizer_url": "http://localhost:8474",
        },
        "seeds": [
            {
                "qualified_name": meta["qname"],
                "source": meta["source"],
                "weight": round(core_result.seeds.seeds[nid], 4),
            }
            for nid, meta in core_result.seeds.metadata.items()
        ],
        "results": results,
    }
    return json.dumps(output, indent=2)


_VALID_QUERY_MODES = frozenset({"dependencies", "symbol_search", "class_hierarchy"})


def query_dependencies_impl(
    entity_name: str,
    direction: str,
    depth: int,
    state: ServerState,
    mode: str = "dependencies",
) -> str:
    """Implementation of query_dependencies tool."""
    mode = (mode or "dependencies").strip().lower()
    logger.info(
        "query_dependencies called: entity='%s' mode=%s direction=%s depth=%d",
        entity_name,
        mode,
        direction,
        depth,
    )

    if mode not in _VALID_QUERY_MODES:
        return json.dumps(
            {
                "error": f"Invalid mode '{mode}'.",
                "hint": (
                    "Use mode='dependencies', 'symbol_search', or 'class_hierarchy'."
                ),
            }
        )

    if _graph_is_empty(state):
        logger.warning("query_dependencies: graph is empty — triggering auto-index")
        _start_background_index(state)
        return json.dumps(_empty_graph_payload())

    project_scope = graph_file_path_scope(state.project_root)

    try:
        if mode == "symbol_search":
            nodes = search_symbols(
                driver=state.driver,
                pattern=entity_name,
                limit=100,
                project_scope=project_scope,
            )
            rel_type = "MATCH"
        elif mode == "class_hierarchy":
            nodes = query_class_hierarchy(
                driver=state.driver,
                class_name=entity_name,
                direction=direction,
                project_scope=project_scope,
            )
            rel_type = None
        else:
            nodes = query_entity_dependencies(
                driver=state.driver,
                entity_name=entity_name,
                direction=direction,
                depth=depth,
            )
            rel_type = None
    except ValueError as exc:
        msg = str(exc)
        if "direction" in msg.lower():
            hint = "Use direction='upstream', 'downstream', or 'both'."
        else:
            hint = (
                "Use get_relevant_context first to confirm the entity name exists."
            )
        return json.dumps({"error": msg, "hint": hint})
    except Exception as exc:
        logger.exception("query_dependencies failed")
        return json.dumps(
            {
                "error": "Dependency query failed",
                "detail": str(exc),
                "hint": "Run 'codegraph doctor' to check system health.",
            }
        )

    if not nodes:
        hints = {
            "dependencies": (
                f"No {direction} dependencies found for '{entity_name}'. "
                "Try direction='both' or depth=2."
            ),
            "symbol_search": (
                f"No symbols matching '{entity_name}'. "
                "Try a shorter pattern or codegraph find."
            ),
            "class_hierarchy": (
                f"No inheritance links for class '{entity_name}'. "
                "Confirm the class name with mode='symbol_search'."
            ),
        }
        return json.dumps(
            {
                "mode": mode,
                "result_count": 0,
                "results": [],
                "hint": hints.get(mode, "No results found."),
            }
        )

    project_root = state.project_root
    serializable = []
    for node in nodes:
        row = {
            "qualified_name": make_relative_qualified_name(
                node.qualified_name,
                node.file_path,
                make_relative_path(node.file_path, project_root),
            ),
            "name": node.name,
            "label": node.label,
            "file_path": make_relative_path(node.file_path, project_root),
        }
        if hasattr(node, "relationship_type"):
            row["relationship_type"] = node.relationship_type or rel_type or ""
        else:
            row["relationship_type"] = rel_type or ""
        serializable.append(row)

    return json.dumps(
        {
            "mode": mode,
            "result_count": len(serializable),
            "results": serializable,
        },
        indent=2,
    )
