# Architecture (summary)

Graph-based context selection: Python → tree-sitter → Neo4j → seeds + PPR → MCP/CLI/visualizer.

**Full detail:** [concepts/architecture.md](concepts/architecture.md)  
**Doc hub:** [README.md](README.md)  
**Decisions:** [DECISIONS.md](../DECISIONS.md)

---

## Pipeline

```
Source code → tree-sitter parse → entity/edge extraction → Neo4j graph
→ seed selection (entity + BM25) → IDF edge reweighting → PPR (GDS)
→ token-budget formatting → MCP / CLI / Visualizer
```

## Defaults (DEC-001)

- `damping_factor`: 0.70
- `top_k`: 30
- `retrieval_mode`: uniform
- Seeds: entity 0.6, BM25 0.3

## MCP

Exactly two tools: `get_relevant_context`, `query_dependencies`.

## Evaluation

SWE-bench Lite — see [thesis/evaluation.md](thesis/evaluation.md) for current Recall@10 (thesis chapter 5 is authoritative).

## Module map

[reference/module-map.md](reference/module-map.md)
