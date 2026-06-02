# CodeGraph Architecture

Graph-based context selection for AI coding agents. Code is modeled as a **structural dependency graph**; relevance is ranked with **Personalized PageRank (PPR)**, not embedding similarity.

See also: [DECISIONS.md](../DECISIONS.md) for binding design choices.

---

## Pipeline overview

```
Source code → tree-sitter parse → entity/edge extraction → Neo4j graph
→ seed selection (entity + BM25) → IDF edge reweighting → PPR (GDS)
→ token-budget formatting → MCP / CLI / Visualizer
```

### Stage 1: Parsing (offline)

- **Engine:** tree-sitter-python
- **Entities:** File, Class, Function, Method (four types only)
- **Identity:** `qualified_name = file_path + '::' + name`

### Stage 2: Graph construction (offline)

- **Storage:** Neo4j + GDS plugin
- **Edges:** `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS_FROM`
- **Call resolution:** imported → same-file → unique global; **ambiguous names → no edge**

### Stage 3: Seed selection (online)

| Signal | Default weight | Source tag |
|--------|----------------|------------|
| Entity match | 0.6 | `entity_match` |
| BM25 | 0.3 | `bm25` |

Compound tokenization splits `CamelCase` / `snake_case` for BM25 recall. Provenance is stored in `PersonalizationVector.metadata`.

### Stage 4: PPR (online)

- **Defaults (iter-2):** `damping_factor=0.70`, `top_k=30`, **uniform** restart
- **IDF reweight:** edge weight `1 / log2(in_degree + 2)` before projection
- **Projection:** `"codegraph"`, UNDIRECTED

### Stage 5: Delivery (online)

- File-level deduplication, source line ranges, token budget
- **MCP:** `get_relevant_context`, `query_dependencies` only

---

## Evaluation (SWE-bench Lite)

| Metric | Approx. value |
|--------|-------------|
| Mean Recall@10 | ~73.3% |
| Mean Recall@5 | ~63.0% |
| Median MRR | 0.33 |

Iterations: baseline (~60% R@10) → uniform restart + d=0.70 (~72%) → IDF + seed refinements (current).

---

## Limitations

- Python-only, static analysis (no type inference)
- Ambiguous calls dropped intentionally
- Batch rebuild model (incremental watch exists but not full incremental graph)
- Dynamic imports / `eval` / monkey-patching invisible

---

## Module map

| Area | Path |
|------|------|
| Parser | `src/codegraph/core/parser/` |
| Graph build | `src/codegraph/core/graph/graph_builder.py` |
| Queries | `src/codegraph/core/graph/queries/` |
| PPR | `src/codegraph/core/graph/ppr.py` |
| Retrieval | `src/codegraph/core/retrieval/` |
| MCP | `src/codegraph/mcp/` |
| CLI | `src/codegraph/cli/commands/` |
| Visualizer API | `src/codegraph/visualizer/` |
| Frontend | `frontend/` |

---

## Deep-dive topics

### Why four entity types?

File-only indexing misses function-level relevance; full AST adds noise and slows PPR. Four types are the tuned middle ground.

### Why uniform restart?

Weighted restart over-trusts a single wrong seed. Uniform mass lets the graph structure reallocate probability to structurally connected seeds.

### Why drop ambiguous CALLS edges?

False edges create spurious shortest paths and dominate PPR neighborhoods. Missing edges are safer than hallucinated dependencies.

---

*Last updated: stabilization pass, June 2026*
