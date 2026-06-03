# AI agent workflows

How coding agents should use CodeGraph. Repo root **[AGENTS.md](../../AGENTS.md)** duplicates the MCP contract; this guide adds workflows and anti-patterns.

---

## Rule 1: Do not guess locations

Before answering "where is X", implementing a feature, or refactoring:

1. Call **`get_relevant_context`** with a clear `task_description`
2. Pass **`mentioned_entities`** when the user names classes/functions
3. Read returned `file_path`, `lines`, and `source_code`

The graph is authoritative; filesystem search is fallback only.

---

## Rule 2: Only two MCP tools exist

| Tool | Use |
|------|-----|
| `get_relevant_context` | Ranked code for a task |
| `query_dependencies` | Callers/callees/imports |

There is **no** MCP tool for: stats, dead code, Cypher, indexing, file search. Use CLI or ask the user to run `codegraph rebuild` / `codegraph stats`.

---

## Workflow patterns

### Implement a feature

```
get_relevant_context(task, mentioned_entities?)
  → read top results
  → edit code
  → (optional) query_dependencies if touching public API
```

### Refactor / rename

```
get_relevant_context(...)     # find definition + usages context
query_dependencies(name, upstream, depth=2)   # all callers
  → apply rename
```

### Debug "wrong context"

Ask user to run or run via shell:

```bash
codegraph explain "<same task>"
```

Check seeds: entity_match vs bm25, missing CALLS edges.

### Impact analysis

```
get_relevant_context
query_dependencies(entity, direction=both, depth=2)
```

---

## Parameters that matter

| Parameter | Guidance |
|-----------|----------|
| `mentioned_entities` | Always pass user-named symbols: `["AuthService", "validate_token"]` |
| `top_k` | 0 = default 30; raise only if token budget allows |
| `token_budget` | 0 = default 6000 |
| `current_file` | Ignored — do not rely on it |
| `include_explanations` | true when user asks "why this file?" |

---

## Empty or error responses

| JSON signal | Agent action |
|-------------|--------------|
| Empty graph / auto-index message | Wait, retry, or tell user: `codegraph rebuild` |
| `hint: run codegraph doctor` | Report connectivity/GDS issue |
| `result_count: 0` | Broaden task description; add `mentioned_entities` |

---

## CLI parity for humans in the loop

| MCP | CLI equivalent |
|-----|----------------|
| `get_relevant_context` | `codegraph query "task" -e Entity` |
| explain paths | `codegraph explain "task"` |
| `query_dependencies` | `codegraph analyze deps Entity -d upstream` |

---

## Anti-patterns

- Calling `query_dependencies` before confirming entity exists
- Using grep alone for cross-file call graphs
- Assuming every `foo()` has a `CALLS` edge (ambiguous calls omitted)
- Changing PPR defaults in docs/code without evaluation
- Adding a third MCP tool without updating DEC-007 and all doc indexes

---

## Cursor / Claude rules

Point custom rules at:

- `docs/README.md` — doc map
- `AGENTS.md` — short MCP reference
- `DECISIONS.md` — before architectural changes

Example rule line: *"For CodeGraph behavior, read docs/guides/agent-workflows.md and follow MCP tool order."*
