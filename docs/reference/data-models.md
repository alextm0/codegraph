# Data models reference

Frozen dataclasses and key runtime types across parser → graph → retrieval → API.

---

## Parser layer (`core/parser/models.py`)

| Type | Frozen | Notes |
|------|--------|-------|
| `FunctionEntity` | yes | Module-level function |
| `ClassEntity` | yes | bases: `tuple[str, ...]` |
| `MethodEntity` | yes | Includes `class_name` |
| `ImportEntity` | yes | Non-stdlib imports |
| `CallEntity` | yes | Unresolved names at parse time |
| `FileEntities` | **no** | Aggregator per file |

---

## Retrieval layer

| Type | Module | Role |
|------|--------|------|
| `SeedNode` | `seed_selection.py` | One seed candidate |
| `PersonalizationVector` | `seed_selection.py` | `seeds: dict[node_id, weight]`, `metadata` |
| `PPRConfig` | `ppr.py` | damping, top_k, retrieval_mode, iterations |
| `PPRResult` | `ppr.py` | Ranked node id + score + properties |
| `RawRetrievalResult` | `pipeline.py` | `seeds` + `ppr_results` bundle |
| `ContextResult` | `post_processing.py` | Formatted snippet for MCP/CLI |
| `ExplainedResult` | `explanations.py` | Explain path + contribution |

---

## Graph query DTOs (`core/graph/queries/models.py`)

| Type | Role |
|------|------|
| `NodeInfo` | qualified_name, name, label, file_path |
| `NodeInfoWithRel` | + relationship_type for dependencies |
| `DeadCodeNode` | Dead code listing |

---

## MCP / visualizer JSON

Not separate Python types in core — built as `dict` in `mcp/tools.py` and `visualizer/models.py` (Pydantic response models for HTTP).

Key MCP result keys: see [mcp.md](mcp.md).

---

## Neo4j node properties (persisted)

Common properties on File/Class/Function/Method:

- `qualified_name` (unique)
- `name`
- `file_path`
- `line_number`, `end_line` (entities)
- Edge property `weight` (float, IDF-adjusted at retrieval)

Exact Cypher MERGE fields: `graph_builder.py` `_create_*` functions.

---

## Config shape

YAML → `dict` via `load_raw_config`. No Pydantic schema — see [config.md](config.md).

---

## Evaluation records

`per_instance.jsonl` lines typically include:

- `instance_id`, `recall_at_5`, `recall_at_10`, `mrr`
- `predicted_files`, `gold_files`
- optional `error`

`summary.json` — `aggregate_metrics()` output + ablation metadata.
