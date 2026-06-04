# AI agent workflows

How coding agents should use CodeGraph. Repo root **[AGENTS.md](../../AGENTS.md)** duplicates the MCP contract; this guide adds workflows and anti-patterns.

---

## Rule 1: Do not guess locations

Before answering "where is X", implementing a feature, or refactoring:

1. If you **know the symbol name**, use `query_dependencies` with `mode="symbol_search"` or CLI `codegraph find <pattern>`
2. For **vague tasks**, call **`get_relevant_context`** with a clear `task_description`
3. Pass **`mentioned_entities`** when the user names classes/functions
4. Read returned `file_path`, `lines`, and `source_code`

The graph is authoritative; filesystem search is fallback only.

---

## Rule 2: Only two MCP tools exist

| Tool | Use |
|------|-----|
| `get_relevant_context` | PPR-ranked code for tasks |
| `query_dependencies` | Dependencies, symbol search, class hierarchy (`mode`) |

There is **no** MCP tool for: stats, dead code, Cypher, indexing. Use CLI or ask the user to run `codegraph rebuild` / `codegraph stats`.

---

## Workflow patterns

### Find a known symbol

```
query_dependencies(entity_name="AuthService", mode="symbol_search", direction="both", depth=1)
```

CLI: `codegraph find AuthService`

### Class inheritance

```
query_dependencies(entity_name="User", mode="class_hierarchy", direction="upstream", depth=1)
```

### Implement a feature

```
get_relevant_context(task, mentioned_entities?)
  → read top results
  → edit code
  → (optional) query_dependencies(mode="dependencies") if touching public API
```

### Refactor / rename

```
get_relevant_context(...)
query_dependencies(name, mode="dependencies", direction="upstream", depth=2)
  → apply rename
```

### Debug "wrong context"

```bash
codegraph explain "<same task>"
```

Or MCP with `include_explanations=true` (default). Check `seeds[]`: `entity_match`, `issue_hint`, `bm25`.

---

## Parameters that matter

| Parameter | Guidance |
|-----------|----------|
| `mentioned_entities` | Pass user-named symbols: `["AuthService", "validate_token"]` |
| `include_explanations` | Default **true**; set false only for lightweight lookups |
| `mode` | `dependencies` (default), `symbol_search`, `class_hierarchy` |
| `top_k` / `token_budget` | 0 = server defaults (30 / 6000) |
| `current_file` | Ignored |

---

## CLI parity

| MCP | CLI |
|-----|-----|
| `get_relevant_context` | `codegraph query "task" -e Entity` |
| explain paths | `codegraph explain "task"` |
| `mode=symbol_search` | `codegraph find <pattern>` |
| `mode=dependencies` | `codegraph analyze deps Entity -d upstream` |
| `mode=class_hierarchy` | (MCP preferred; no dedicated CLI yet) |

---

## Anti-patterns

- Running full PPR when `symbol_search` would suffice
- Calling `query_dependencies` with wrong entity name (use `symbol_search` first)
- Ignoring `seeds[]` / `explanation` when rankings look wrong
- Using grep alone for cross-file call graphs
- Assuming every `foo()` has a `CALLS` edge (ambiguous calls omitted)

---

## Cursor / Claude rules

`.cursor/rules/codegraph-docs.mdc` points agents at `docs/README.md` and `DECISIONS.md`.
