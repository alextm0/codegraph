# Explainability

How CodeGraph answers **why** a file ranked highly. Shared logic for CLI, MCP, and visualizer.

**Code:** `src/codegraph/core/retrieval/explanations.py`, `path_tracing.py`, `trace.py`

---

## Explained result fields

Each `ExplainedResult` contains:

| Field | Meaning |
|-------|---------|
| `rank` | 1-based rank after file deduplication |
| `ppr_score` | PageRank score |
| `seed_qualified_names` | Seeds on reasoning path |
| `seed_sources` | `entity_match` or `bm25` |
| `reasoning_path` | Human-readable path string |
| `path_ids` | Node qualified names along shortest path |
| `contribution` | `lexical`, `graph`, or `both` |

**Lexical** = reached mainly from entity/BM25 seeds. **Graph** = propagated through CALLS/IMPORTS structure.

---

## Interfaces

| Interface | How |
|-----------|-----|
| CLI | `codegraph explain "task"` |
| MCP | `get_relevant_context(..., include_explanations=true)` |
| CLI trace | `codegraph query "task" --trace` → JSON via `build_retrieval_trace()` |
| Visualizer | Explain panel after `/api/query` |

---

## Algorithm sketch

1. Run `run_core_retrieval` → seeds + PPR results
2. Deduplicate to file-level top-k
3. `batch_trace_paths` — shortest paths from seed nodes to each result in Neo4j
4. Classify contribution from seed metadata vs graph-only reachability

---

## Debugging retrieval failures

Use explain when:

- Results are utility modules (logging, typing)
- Expected file not in top 10
- Comparing agent task vs benchmark issue text

Check:

- Were seeds `entity_match` or only `bm25`?
- Is `contribution` lexical but wrong synonym?
- Is gold file unreachable (zero CALLS path from any seed)? — thesis “reachability bottleneck”

---

## Visualizer URL

MCP returns `summary.visualizer_url` (`http://localhost:8474`) so users can explore the same graph interactively after agent retrieval.
