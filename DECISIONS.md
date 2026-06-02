# CodeGraph Decision Log

Technical decisions with **Status: ACTIVE** are binding. Do not override without updating this file.

---

## DEC-001: PPR defaults (iter-2 tuned)

**Status:** ACTIVE  
**Date:** 2025  
**Context:** SWE-bench Lite tuning showed lower damping and uniform restart improve recall.

**Decision:**
- `damping_factor`: **0.70** (not 0.85)
- `top_k`: **30** (not 20)
- `retrieval_mode`: **uniform** restart (equal mass per seed)

**Rationale:** Uniform restart lets graph structure vote on seed relevance; wrong seeds dissipate mass instead of dominating.

---

## DEC-002: Frozen dataclasses for entity models

**Status:** ACTIVE  
**Context:** Entity models are immutable value objects parsed from AST.

**Decision:** Use `@dataclass(frozen=True)` for parser entities. No Pydantic in core parsing.

---

## DEC-003: Four-entity graph model

**Status:** ACTIVE  
**Context:** Granularity trade-off between file-only (too coarse) and full AST (too noisy).

**Decision:** Index exactly four node types: **File**, **Class**, **Function**, **Method**.

**Identity:** `qualified_name = file_path + '::' + name`

---

## DEC-004: Ambiguous call resolution — drop edge

**Status:** ACTIVE  
**Context:** False CALLS edges hurt PPR more than missing edges.

**Decision:** Three-level resolution (imported → same-file → unique global). If a callee name matches **multiple** targets, **create no edge**.

---

## DEC-005: IDF edge reweighting before PPR

**Status:** ACTIVE  
**Context:** Utility functions (`logger`, `isinstance`) act as relevance sinks.

**Decision:** Weight edges by `1 / log2(in_degree + 2)` before GDS projection. Applied on every retrieval via `ensure_graph_ready()`.

---

## DEC-006: Seed signal weights

**Status:** ACTIVE  
**Context:** Personalization vector combines two signals (configurable in `config.yaml`). Active-file hints were removed because the currently open file is not a reliable relevance signal.

**Decision:** Default weights:
- `entity_match`: 0.6
- `bm25`: 0.3

Store provenance in `PersonalizationVector.metadata[nid]["source"]`.

---

## DEC-007: MCP surface — exactly two tools

**Status:** ACTIVE  
**Decision:** MCP exposes only:
1. `get_relevant_context`
2. `query_dependencies`

Stats, dead-code, and raw Cypher are **CLI-only**.

---

## DEC-008: Neo4j writes — UNWIND + MERGE

**Status:** ACTIVE  
**Decision:** All graph writes use batched `UNWIND` + `MERGE`. No per-entity `CREATE` loops.

---

## DEC-009: Edge types in projection

**Status:** ACTIVE  
**Decision:** Four relationship types: `CALLS`, `IMPORTS`, `CONTAINS`, `INHERITS_FROM`. `CO_LOCATED` removed in iter-3.

GDS projection name: `"codegraph"`, orientation `UNDIRECTED`, base weight 1.0.

---

## DEC-010: Credentials not in config.yaml

**Status:** ACTIVE  
**Decision:** Neo4j password from `NEO4J_PASSWORD` env var or `.env` file only.

---

## Template for new decisions

```
## DEC-XXX: Title

**Status:** ACTIVE | SUPERSEDED  
**Date:** YYYY-MM-DD  
**Context:** ...

**Decision:** ...

**Rationale:** ...
```
