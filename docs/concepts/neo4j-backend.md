# Neo4j backend

CodeGraph uses **one** database backend: **Neo4j 5.x** + **Graph Data Science (GDS)**. No Kuzu/FalkorDB/Ladybug (unlike CodeGraphContext).

**Code:** `src/codegraph/core/graph/`

---

## Connection and singleton

| Module | Role |
|--------|------|
| `connection.py` | `Neo4jConfig`, `create_driver`, `load_config`, connectivity check |
| `database.py` | `DatabaseManager` singleton — driver lifecycle for CLI/MCP/viz |

Password resolution order:

1. `NEO4J_PASSWORD` environment variable
2. `.env` via `python-dotenv`
3. Never from `config.yaml` (DEC-010)

Config URI/username from `config.yaml` → `neo4j` section.

---

## Schema constraints

`ensure_constraints()` creates **unique** constraints on `qualified_name` per label:

- File, Function, Class, Method

Enables idempotent `MERGE` during batch writes.

---

## Write patterns (DEC-008)

- `clear_database()` — `DETACH DELETE` all nodes (full rebuild)
- `delete_file_entities(file_path)` — incremental watch: remove one file’s nodes
- `build_graph(driver, all_entities)` — batched UNWIND+MERGE for nodes and edges

---

## GDS projection

| Constant | Value |
|----------|-------|
| Projection name | `"codegraph"` |
| Orientation | `UNDIRECTED` (default; ablations test NATURAL/REVERSE) |
| Relationship types | CONTAINS, CALLS, IMPORTS, INHERITS_FROM |

`project_graph()` / `drop_projection()` in `ppr.py`.  
`ensure_graph_ready()` in `pipeline.py` reapplies IDF weights and recreates projection each retrieval.

---

## Cypher query layer (`queries/`)

| Module | Functions |
|--------|-----------|
| `dependencies.py` | `query_entity_dependencies`, callers/callees, pattern search |
| `stats.py` | `count_nodes_by_label`, `count_edges_by_type`, `find_dead_code` |
| `subgraph.py` | Full graph, subgraph by prefix, node detail, file entities |
| `path_tracing.py` | Shortest paths for explainability |
| `models.py` | `NodeInfo`, `DeadCodeNode`, etc. |

MCP `query_dependencies` → `query_entity_dependencies()`.

---

## Dead code definition

`find_dead_code`: Functions/Methods with **no incoming `CALLS`** and not `__init__` / `main` / test-like names (see Cypher in `stats.py`). CLI `analyze dead-code` and visualizer `/api/dead-code`.

Heuristic only — dynamic entry points (Flask routes, callbacks) may appear “dead”.

---

## Doctor checks

See [../reference/troubleshooting.md](../reference/troubleshooting.md):

- `config_file`, `project_root`, `neo4j_password`
- `neo4j_connectivity`, `gds_plugin`
- `graph_index`, `graph_project_alignment`
- `tree_sitter`

---

## Evaluation harness connection

`evaluation/swe_bench_runner.py` creates its own driver via `load_config` / `create_driver`, clears DB per repo group, builds graph, runs retrieval — same core as production but scripted batch mode.
