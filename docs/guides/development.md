# Developing CodeGraph

Guide for contributors and agents implementing features.

---

## Before you code

1. Read [DECISIONS.md](../../DECISIONS.md) — ACTIVE decisions are binding
2. Read [../concepts/architecture.md](../concepts/architecture.md) and [../reference/module-map.md](../reference/module-map.md)
3. For retrieval changes: plan SWE-bench re-evaluation (see [../thesis/evaluation.md](../thesis/evaluation.md))

---

## Code conventions (from CLAUDE.md)

- Type hints on all public functions
- Docstrings on public APIs
- Frozen dataclasses in parser (no Pydantic in core)
- Functions ≤ 50 lines — split if longer
- Dependency injection, no global Neo4j driver in core logic
- Neo4j writes: **UNWIND + MERGE** only

---

## Tests

```bash
python -m pytest tests/unit/ -q     # no Neo4j required
python -m pytest tests/ -v          # integration; Neo4j tests skip if DB down
```

Fixtures: `tests/fixtures/user_auth/` (primary), `tests/fixtures/flask/`.

MCP integration: `tests/integration/mcp/test_server.py`.

Mark Neo4j-dependent tests with project’s `@neo4j_required` pattern.

---

## Common change locations

| Task | Where |
|------|-------|
| New Python syntax support | `core/languages/python/extractors.py` |
| New edge type | parser + `graph_builder.py` + projection in `ppr.py` |
| Seed signal | `seed_selection.py`, `config.yaml`, docs |
| PPR tuning | `ppr.py`, `config.yaml`, evaluation harness |
| New CLI command | `cli/commands/`, register in `cli/main.py` |
| New MCP tool | **currently forbidden** (2 tools only) |
| Visualizer API | `visualizer/`, `frontend/src/api/` |

---

## Adding a new CLI-only command

Allowed without expanding MCP surface. Update:

- `src/codegraph/cli/main.py`
- [../reference/cli.md](../reference/cli.md)
- [../QUICK_REFERENCE.md](../QUICK_REFERENCE.md) if user-facing

---

## Documentation duty

When behavior changes, update in the **same PR**:

- Relevant `docs/concepts/` or `docs/reference/` page
- `DECISIONS.md` if a new binding choice
- `AGENTS.md` if MCP contract changes
- Thesis chapter if evaluation claims change

See [../UPDATING_DOCS.md](../UPDATING_DOCS.md).

---

## Performance notes

- Batch Neo4j operations; never loop `CREATE` per node
- Do not parallelize tree-sitter unless parse time > ~10s
- IDF + projection on each retrieval is by design — optimize only with benchmarks
ith benchmarks
