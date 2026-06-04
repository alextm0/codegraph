# Troubleshooting

Start with:

```bash
codegraph doctor
```

Structured JSON checks are also available from `GET /api/doctor` and `run_doctor_checks()` for tooling.

### Doctor check names

| Check | Meaning |
|-------|---------|
| `config_file` | config.yaml readable |
| `project_root` | Path exists |
| `neo4j_password` | `NEO4J_PASSWORD` set |
| `neo4j_connectivity` | Bolt OK |
| `gds_plugin` | GDS version callable |
| `graph_index` | Node count > 0 |
| `graph_project_alignment` | Sample paths under project_root |
| `tree_sitter` | Parser importable |

---

## Neo4j not reachable

**Symptoms:** Connection errors in `doctor`, `stats`, MCP failures.

**Fix:**

1. Start Neo4j Desktop DBMS or `neo4j start`
2. Confirm Bolt URI matches `config.yaml` (`neo4j://localhost:7687`)
3. Set `NEO4J_PASSWORD` in `.env` (run `codegraph init` if missing)

---

## GDS plugin missing

**Symptoms:** Doctor reports GDS unavailable; PPR errors mentioning projection/PageRank.

**Fix:**

- Neo4j Desktop → your database → **Plugins** → install **Graph Data Science**
- Restart database

---

## Empty graph / no MCP results

**Symptoms:** `result_count: 0`, message about empty index, auto-index in background.

**Fix:**

```bash
codegraph rebuild
codegraph stats
```

Confirm `project_root` points at the codebase you expect.

---

## Wrong or irrelevant context

**Symptoms:** Utility files, tests, or unrelated modules rank high.

**Diagnose:**

```bash
codegraph explain "same task description"
```

**Fixes:**

- Pass explicit entities: `codegraph query "task" -e ClassName`
- Add `seed_selection.exclude_seed_paths` for test directories
- Remember: ambiguous calls have **no** edge — graph may not connect modules you expect

---

## MCP not visible in IDE

**Fix:**

```bash
codegraph install
codegraph status
```

Restart IDE. Verify config path in MCP JSON matches real `config.yaml`.

Manual setup: [../getting-started/mcp-setup.md](../getting-started/mcp-setup.md).

---

## Visualizer blank or 404

**Fix:**

- Run `codegraph visualize` (builds/serves frontend bundle)
- Check port 8474 not in use; try `--port`
- For UI dev: `--dev` + `cd frontend && npm run dev`

---

## Tests fail on Neo4j

Integration tests skip when DB is down — expected on laptops without Neo4j. CI should start Neo4j or run `pytest tests/unit/` only.

---

## Configuration mistakes

| Mistake | Result |
|---------|--------|
| Password in `config.yaml` | Ignored / doctor warning — use `.env` |
| Wrong `project_root` | Empty or foreign graph |
| Old PPR values (0.85, top_k 20) | Suboptimal recall — use DEC-001 defaults |
