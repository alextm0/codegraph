# Design decisions index

**Authoritative file:** [DECISIONS.md](../../DECISIONS.md) at repo root.

Agents **must** read ACTIVE decisions before proposing architectural alternatives. This page is an index only — full rationale stays in `DECISIONS.md`.

| ID | Topic | Summary |
|----|-------|---------|
| DEC-001 | PPR defaults | d=0.70, top_k=30, uniform restart |
| DEC-002 | Entity models | Frozen dataclasses, no Pydantic in parser |
| DEC-003 | Graph granularity | Four node types: File, Class, Function, Method |
| DEC-004 | Call resolution | Ambiguous callee → no CALLS edge |
| DEC-005 | IDF reweighting | `1/log2(in_degree+2)` before PPR |
| DEC-006 | Seed weights | entity 0.6, BM25 0.3; no active-file seed |
| DEC-007 | MCP surface | Exactly two tools |
| DEC-008 | Neo4j writes | UNWIND + MERGE batches |
| DEC-009 | Edge types | CALLS, IMPORTS, CONTAINS, INHERITS_FROM; projection `codegraph` |
| DEC-010 | Secrets | Password in env/.env only |

**New decision workflow:** append to `DECISIONS.md` using template there; add row to this table; update affected concept docs.

**Conflict:** If code contradicts ACTIVE decision, flag to user — do not silently override.
