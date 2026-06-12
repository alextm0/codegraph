# Module map (`src/codegraph/`)

Per-file responsibilities. See [PROJECT_LAYOUT.md](../PROJECT_LAYOUT.md) for full repo tree.

---

## `core/parser/`

| File | Role |
|------|------|
| `service.py` | `parse_file`, `parse_directory`, orchestration |
| `registry.py` | LanguageRegistry, LanguageSpec |
| `node_utils.py` | Source text, docstrings, signatures, stdlib filter |
| `models.py` | Frozen entity dataclasses, `FileEntities` |
| `base.py` | Parser abstractions |

---

## `core/languages/`

| File | Role |
|------|------|
| `registration.py` | register_all_languages() |
| `python/parser.py` | PythonParser implementation |
| `python/resolver.py` | PythonResolver implementation |
| `python/extractors.py` | tree-sitter walks: defs, calls, imports |

Doc: [../concepts/parser.md](../concepts/parser.md)

---

## `core/graph/`

| File | Role |
|------|------|
| `graph_builder.py` | `build_graph`, `clear_database`, UNWIND+MERGE, two-pass edges |
| `resolver_interface.py` | LanguageResolver ABC |
| `ppr.py` | GDS projection, uniform/weighted PPR, `PPRConfig` |
| `connection.py` | Driver factory, config load |
| `database.py` | `DatabaseManager` singleton |
| `utils.py` | Path normalization |
| `queries/dependencies.py` | MCP/CLI dependency traversal |
| `queries/stats.py` | Counts, dead code, hub files |
| `queries/subgraph.py` | Viz graph payloads, node detail |
| `queries/path_tracing.py` | Shortest paths for explain |
| `queries/models.py` | `NodeInfo`, `DeadCodeNode` |

Doc: [../concepts/neo4j-backend.md](../concepts/neo4j-backend.md), [../concepts/call-resolution.md](../concepts/call-resolution.md)

---

## `core/retrieval/`

| File | Role |
|------|------|
| `pipeline.py` | `run_core_retrieval`, `ensure_graph_ready` |
| `seed_selection.py` | BM25, entity match, `PersonalizationVector` |
| `post_processing.py` | IDF, `format_context`, tiktoken budget |
| `explanations.py` | `build_explained_results` |
| `trace.py` | `build_retrieval_trace` for `--trace` |

Doc: [../concepts/retrieval-pipeline.md](../concepts/retrieval-pipeline.md), [../concepts/explainability.md](../concepts/explainability.md)

---

## `mcp/`

| File | Role |
|------|------|
| `server.py` | FastMCP, tool decorators, lifespan |
| `server_config.py` | `ServerState`, config path resolution |
| `tools.py` | Tool implementations, background index |
| `prompts.py` | `LLM_SYSTEM_PROMPT` |

Doc: [mcp.md](mcp.md)

---

## `cli/`

| File | Role |
|------|------|
| `main.py` | Typer app, all command registration |
| `cli_helpers.py` | Re-exports command helpers |
| `commands/build.py` | `rebuild_helper` (+ progress callback for viz) |
| `commands/init.py` | Setup wizard, clone, write config |
| `commands/install.py` | MCP JSON for Claude/Gemini |
| `commands/query.py` | Query + JSON/trace output |
| `commands/explain.py` | Explain tables |
| `commands/doctor.py` | `run_doctor_checks` |
| `commands/status.py` | Status + stats display |
| `commands/visualize.py` | Start uvicorn app |
| `commands/watch.py` | File watcher entry |
| `commands/_shared.py` | DB init, build timestamps |

Doc: [cli.md](cli.md)

---

## `visualizer/`

| File | Role |
|------|------|
| `app.py` | FastAPI factory, static mount, watcher |
| `routes.py` | All `/api/*` and `/ws/status` |
| `query_service.py` | Query + dependency graph for UI |
| `context.py` | `VisualizerContext` shared state |
| `models.py` | Pydantic request/response types |
| `graph_filter.py` | Hide excluded paths in UI |
| `file_source.py` | Resolve file on disk |

Doc: [visualizer-api.md](visualizer-api.md), [../guides/visualization.md](../guides/visualization.md)

---

## `watcher/`

| File | Role |
|------|------|
| `file_watcher.py` | watchdog integration |
| `incremental.py` | `update_file_in_graph` — delete+parse+merge one file |

Doc: [../concepts/how-it-works.md](../concepts/how-it-works.md)

---

## `utils/`

| File | Role |
|------|------|
| `config.py` | YAML load/save, `resolve_project_root`, signal weights |
| `paths.py` | Relative paths for MCP JSON |
| `ignore.py` | `.cgignore` pathspec |
| `graph_helpers.py` | `verify_graph_project_root` (doctor) |
| `tree_sitter_manager.py` | Shared parser lifecycle |
| `logging.py` | CLI logging setup |

---

## `evaluation/` (repo root, not under src)

| File | Role |
|------|------|
| `swe_bench_runner.py` | Main benchmark orchestrator |
| `ablations.py` | `ABLATIONS` configs |
| `metrics.py` | recall@k, MRR, aggregate |
| `dataset.py` | Instance loading, grouping |
| `repo_manager.py` | Git clone/cache/checkout |
| `gold_patch_parser.py` | Gold file extraction |
| `baselines.py` | BM25-only etc. |
| `dashboard/` | Textual monitoring UI |

Doc: [../guides/evaluation-harness.md](../guides/evaluation-harness.md)

---

## `frontend/` (repo root)

React UI — see [../guides/visualization.md](../guides/visualization.md).

---

## Docs for agents

| Path | Role |
|------|------|
| `docs/README.md` | Hub |
| `AGENTS.md` | Short MCP contract |
