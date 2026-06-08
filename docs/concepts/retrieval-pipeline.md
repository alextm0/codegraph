# Retrieval pipeline

Online path from natural-language task → ranked source snippets. Orchestrator: `src/codegraph/core/retrieval/pipeline.py` (`run_core_retrieval`, `run_retrieval_pipeline`).

---

## Steps

```
task_description + mentioned_entities
  → prepare_bm25_index()
  → extract_seeds()           # entity_match + issue_hint + BM25
  → apply_idf_weights()       # optional, default on
  → project_graph("codegraph")
  → run_ppr_from_node_ids()   # uniform restart
  → format_context()          # token budget, dedupe
```

---

## Seed selection

**Inputs:**

- `task_description` — issue text or agent task
- `mentioned_entities` — explicit names from user/agent
- Auto-extracted identifiers from task text (`extract_entity_names`)

**Signals:**

| Config key | Default | Role |
|------------|---------|------|
| `seed_selection.entity_match_weight` | 0.6 | Graph nodes whose names match mentioned/auto entities |
| `seed_selection.bm25_weight` | 0.3 | Top BM25 nodes from task text |
| `seed_selection.issue_hint_weight` | 0.2 | Nodes under file paths mentioned in issue text |
| `seed_selection.bm25_top_n` | 10 | BM25 candidate cap |

Provenance stored in `PersonalizationVector.metadata[nid]["source"]`.

**Excluded paths:** `seed_selection.exclude_seed_paths` — nodes under these paths are not used as BM25/entity seeds (e.g. `tests/`).

**Restart mode:** `ppr.retrieval_mode: uniform`
 — equal mass per seed node so one bad seed cannot dominate.

---

## IDF reweighting

Before projection, in-degree IDF down-weights hub nodes (`logger`, helpers):

```
weight = 1 / log2(in_degree + 2)
```

Applied in `apply_idf_weights()`; base weights restored via `reset_base_weights()` after PPR.

---

## PPR

| Parameter | Default | Config path |
|-----------|---------|-------------|
| Damping | 0.70 | `ppr.damping_factor` |
| Top results | 30 | `ppr.top_k` |
| Max iterations | 20 | `ppr.max_iterations` |
| Tolerance | 1e-7 | `ppr.tolerance` |

Implementation: `src/codegraph/core/graph/ppr.py`, GDS `graph.project` + PageRank.

**Do not change defaults** without re-running SWE-bench evaluation harness.

---

## Post-processing

- Map PPR node scores to entities
- File-level deduplication where applicable
- Attach `source_code` and line ranges from disk (`project_root`)
- Enforce `token_budget` (MCP/CLI default 6000)

`format_context()` in `post_processing.py`.

---

## Explainability

**CLI:** `codegraph explain "task"` — seeds table + reasoning paths.

**MCP:** `include_explanations=true` on `get_relevant_context` — adds `explanation` per result and `seeds[]`.

Logic: `src/codegraph/core/retrieval/explanations.py`.

---

## Interfaces sharing one core

| Interface | Entry |
|-----------|-------|
| MCP | `get_relevant_context_impl` in `mcp/tools.py` |
| CLI | `query_helper`, `explain_helper` |
| Visualizer API | Uses same `run_core_retrieval` via visualizer routes |

Never duplicate ranking logic in the frontend — change `pipeline.py` and seed/PPR modules only.

---

## Structured trace (`--trace`)

CLI `codegraph query "task" --trace` emits JSON from `build_retrieval_trace()`:

- `seeds[]` with weights and sources
- `ppr_config` snapshot
- `top_results[]` with explain paths

Same underlying logic as [explainability.md](explainability.md).

---

## Failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Empty results | No index / wrong `project_root` | `codegraph rebuild` |
| GDS error | Plugin missing | Neo4j Desktop → GDS plugin |
| All utility files | Bad seeds or missing CALLS | `codegraph explain`, mention entities |
| Exception in MCP | Neo4j down | `codegraph doctor` |
