# Indexing a codebase

## Full rebuild (normal)

```bash
codegraph rebuild
```

1. Clears existing graph data for the project
2. Parses all Python under `project_root`
3. Writes nodes/edges in batches

Run after: cloning, large refactors, changing `project_root`, or when `stats` shows zero nodes.

Timestamp written to config (`project_history` / build metadata) — see `status` output.

---

## Excludes

**config.yaml:**

```yaml
exclude_patterns:
  - __pycache__
  - .venv
  - .git
  - .codegraph_cache/
  - tests/fixtures/
```

**Optional `.cgignore`** at project root (same semantics as gitignore pathspecs).

**Seed-only excludes** (still indexed, not used as PPR seeds):

```yaml
seed_selection:
  exclude_seed_paths:
    - tests/
    - test_
```

---

## Verify index

```bash
codegraph stats
codegraph status
```

Expect non-zero counts for File/Class/Function/Method and relationship types.

---

## Watch mode

```bash
codegraph watch
```

Keeps graph updated on save. For thesis demos or CI, prefer explicit `rebuild` so state is reproducible.

---

## Multiple projects

`config.yaml` supports `project_history` with named paths (e.g. under `projects/`). `init` can clone GitHub repos. Switch `project_root` and run `rebuild` when changing target codebase.

---

## MCP background indexing

Empty graph + MCP call → background thread indexes automatically. For agents, document: wait and retry, or run `codegraph rebuild` first.

Implementation: `_start_background_index` in `src/codegraph/mcp/tools.py`.
