# Architecture (summary)

Structural context retrieval for AI coding agents.

**Full detail:** [concepts/architecture.md](concepts/architecture.md)  
**Doc hub:** [README.md](README.md)  
**Decisions:** [DECISIONS.md](../DECISIONS.md)

---

## The Mental Model

CodeGraph is conceptualized as two distinct functional flows:

- **Indexing Path (Offline)**: Parses Python source code into a structural Neo4j graph of calls, imports, and inheritance.
- **Retrieval Path (Online)**: Traverses the graph from task-specific seeds using Personalized PageRank to find relevant context.

## Pipeline

```
Indexing Path: Source code → tree-sitter parse → entity/edge extraction → Neo4j graph
Retrieval Path: User Task → seed selection (entity + BM25) → IDF edge reweighting → PPR (GDS) → token-budget formatting → MCP / CLI / Visualizer
```

## Trust & Transparency

CodeGraph provides three core trust signals:
1. **Seed Provenance**: Explicitly identifying which "seeds" triggered a result.
2. **Traceable Paths**: Explaining *why* code was retrieved via the `explain` interface.
3. **Shared Retrieval Core**: Identical ranking logic across CLI, MCP, and visualizer.

## Defaults

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
