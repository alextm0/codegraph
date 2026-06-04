# AGENTS.md — AI Agent Architecture Guide

This file helps AI agents understand the CodeGraph system's mental model and current state.

**Full documentation:** [`docs/README.md`](docs/README.md) — concepts, CLI/MCP reference, guides, thesis alignment. Prefer that tree as source of truth over this short summary.

## System Philosophy

Code is treated as a **structural graph**, not a text blob. Relevance is determined by graph connectivity (Personalized PageRank) rather than embedding similarity.

## The Pipeline

```
Source code
  → tree-sitter parsing       (src/codegraph/core/parser)
  → entity/edge extraction    (Functions, Classes, Methods, Files;
                                CALLS, IMPORTS, CONTAINS, INHERITS_FROM edges)
  → Neo4j graph build         (src/codegraph/core/graph)
  → PPR seed selection        (src/codegraph/core/retrieval/seed_selection.py)
  → Personalized PageRank     (src/codegraph/core/graph/ppr.py)
  → IDF post-processing       (src/codegraph/core/retrieval/post_processing.py)
  → MCP server response       (src/codegraph/mcp)
```

## MCP Tools (exactly 2)

**`get_relevant_context`** — PPR-ranked code for tasks and bug reports.
- Input: `task_description`, `mentioned_entities` (list or null), `top_k` (0 = default 30), `token_budget` (0 = default 6000), `include_explanations` (default **true**). `current_file` is ignored.
- Output: JSON with `summary`, `seeds[]`, `results[]` (entity, file, lines, score, source_code; optional `explanation` per result)
- Empty graph returns `hint: "run codegraph rebuild"`
- Pipeline errors return `error` + `hint: "run codegraph doctor"`

**`query_dependencies`** — fast structural lookups (also symbol search and class hierarchy).
- Input: `entity_name`, `direction` (upstream/downstream/both), `depth` (1 or 2), `mode` (`dependencies` | `symbol_search` | `class_hierarchy`)
- `symbol_search`: `entity_name` is a substring pattern; ignores depth
- `class_hierarchy`: inheritance ancestors (upstream) or subclasses (downstream)
- Output: JSON with `mode`, `result_count`, `results[]`

There are **no other MCP tools**. `get_graph_stats`, `find_dead_code`, `execute_cypher_query` exist only as CLI commands.

## Key Files

| File | Purpose |
|------|---------|
| `src/codegraph/core/parser/python_parser.py` | tree-sitter entity extraction |
| `src/codegraph/core/graph/graph_builder.py` | UNWIND+MERGE Neo4j writes |
| `src/codegraph/core/graph/resolution.py` | CALLS/IMPORTS resolution (ambiguous → no edge) |
| `src/codegraph/core/graph/ppr.py` | PPRConfig, run_ppr_from_node_ids |
| `src/codegraph/core/retrieval/seed_selection.py` | entity + BM25 + issue path hint seeds |
| `src/codegraph/core/retrieval/post_processing.py` | IDF weighting, token budget |
| `src/codegraph/core/retrieval/pipeline.py` | run_core_retrieval |
| `src/codegraph/mcp/server.py` | FastMCP lifespan, ServerState |
| `src/codegraph/mcp/tools.py` | get_relevant_context_impl, query_dependencies_impl |
| `src/codegraph/visualizer/routes.py` | Visualizer REST/WS API |
| `src/codegraph/watcher/incremental.py` | Per-file graph updates |
| `evaluation/swe_bench_runner.py` | SWE-bench Lite harness |
| `DECISIONS.md` | Binding design decisions |
| `docs/README.md` | Full documentation index |

## PPR Defaults (iter-2 tuned — do not change without benchmarking)

- `damping_factor`: 0.70
- `top_k`: 30
- `retrieval_mode`: "uniform"

## Architecture Patterns

- **Node identity**: `qualified_name = file_path + '::' + name`
- **All Neo4j writes**: UNWIND+MERGE (idempotent, batched)
- **Graph projection**: `"codegraph"` (UNDIRECTED, weight=1.0 on all edge types)
- **Edge types**: CALLS, IMPORTS, CONTAINS, INHERITS_FROM (CO_LOCATED removed in iter-3 cleanup)
- **Password**: never in config.yaml — read from `NEO4J_PASSWORD` env var or `.env` file
- **GDS tests**: skip gracefully with `@neo4j_required` when Neo4j not running

## CLI Commands

```bash
codegraph init                              # Interactive setup wizard
codegraph install                           # Register MCP with Claude Code or Desktop
codegraph rebuild                           # Clear + parse + build graph
codegraph status                            # Project root, graph counts, last build, MCP registration
codegraph stats                             # Node/edge counts table
codegraph doctor                            # Health checks with fix hints
codegraph query "task" --entity EntityName  # Run retrieval pipeline
codegraph explain "task"                    # Show seeds + PPR reasoning paths
codegraph find <pattern>                    # Fast symbol/path search
codegraph visualize                         # D3 force graph in browser (port 8474)
codegraph analyze deps <Name>               # Dependency traversal
codegraph analyze dead-code                 # Unreachable entities
codegraph watch                             # Incremental file-change updates
codegraph serve                             # Start MCP server (stdio)
```

## Testing

```bash
python -m pytest tests/unit/ -q         # 236 unit tests, no Neo4j needed
python -m pytest tests/ -v               # All tests (Neo4j tests skip if DB not running)
```

## Decisions

All design decisions are in `DECISIONS.md`. Read it before suggesting architectural changes.
Never silently override a decision with Status: ACTIVE.
