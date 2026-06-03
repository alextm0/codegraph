# Code graph model

CodeGraph uses a **property graph** in Neo4j: four node labels and four relationship types. This is intentionally smaller than multi-language tools like CodeGraphContext.

---

## Node labels

| Label | Meaning | Key properties |
|-------|---------|----------------|
| `File` | A `.py` source file | `path`, `qualified_name` |
| `Class` | Class definition | `name`, `qualified_name`, `file_path`, line range |
| `Function` | Module-level function | same pattern |
| `Method` | Method on a class | same pattern |

**Identity rule (DEC-003):**

```
qualified_name = <file_path> + '::' + <name>
```

Example: `src/auth/service.py::AuthService`

There is no separate `Module` or `Repository` node — package structure appears via `IMPORTS` and file paths.

---

## Relationship types

| Type | Typical pattern | Semantics |
|------|-----------------|-----------|
| `CONTAINS` | File → Class/Function; Class → Method | Nesting / scope |
| `IMPORTS` | File → File (or resolved target) | Static import edges |
| `CALLS` | Function/Method → Function/Method | Resolved invocation (may be absent if ambiguous) |
| `INHERITS_FROM` | Class → Class | Base class link |

**Removed:** `CO_LOCATED` (iter-3 cleanup, DEC-009).

---

## Call resolution (static)

When parser sees a call `foo()`:

1. Resolve via imports in the same file
2. Else same-file definition
3. Else globally unique name in the index
4. If multiple candidates → **no `CALLS` edge** (DEC-004)

Agents should not assume every runtime call appears in the graph.

---

## GDS projection

For PPR, relationships are projected as an **undirected** graph named `codegraph` with base weight `1.0`, then IDF-adjusted per retrieval run.

---

## Example (conceptual)

```
File: src/api/routes.py
  CONTAINS → Function: handle_login
    CALLS → Method: AuthService.authenticate
      (AuthService in src/auth/service.py)
```

---

## Querying from agents

- **Relevance ranking:** MCP `get_relevant_context` (PPR), not manual Cypher
- **Local neighborhood:** MCP `query_dependencies` or `codegraph analyze deps`
- **Raw Cypher / stats:** CLI only (`codegraph stats`, internal queries) — not exposed on MCP

Schema implementation: `src/codegraph/core/graph/graph_builder.py`, `src/codegraph/core/graph/queries/`.
