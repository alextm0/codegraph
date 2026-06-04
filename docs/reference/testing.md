# Testing guide

**Code:** `tests/`

---

## Quick commands

```bash
python -m pytest tests/unit/ -q          # fast, no Neo4j
python -m pytest tests/ -v               # full; Neo4j tests skip if down
python -m pytest tests/integration/mcp/ -v
```

CI (`.github/workflows/ci.yml`): `pip install -e ".[dev]"` + `pytest tests/ -v` on Ubuntu Python 3.12.

---

## Layout

| Directory | Contents |
|-----------|----------|
| `tests/unit/` | Parser, retrieval, graph mocks, CLI, MCP config, visualizer units |
| `tests/integration/` | MCP server, visualizer HTTP |
| `tests/fixtures/user_auth/` | Small auth-themed Python project (primary E2E fixture) |
| `tests/fixtures/flask/` | Upstream Flask clone for large-scale tests (norecursed by pytest) |

`pyproject.toml` sets `norecursedirs = ["tests/fixtures"]` so Flask’s own tests are not collected.

---

## Neo4j tests

`tests/conftest.py`:

- Loads `tests/config.yaml` for bolt credentials
- `@neo4j_required` / `pytest.mark.neo4j` — skip if `bolt://localhost:7687` unreachable
- `clean_db` fixture — wipes DB before/after graph integration tests
- `DatabaseManager` reset autouse — avoids singleton leakage

**Local dev:** run Neo4j Desktop for integration tests; otherwise unit-only is fine.

---

## Key test areas

| Area | Example path |
|------|----------------|
| Seed selection / BM25 | `tests/unit/core/retrieval/test_seed_selection.py` |
| PPR config | `tests/unit/core/graph/test_ppr.py` |
| Resolution | `tests/unit/core/graph/` |
| MCP tools (mocked) | `tests/integration/mcp/test_server_mocked.py` |
| Evaluation metrics | `tests/unit/evaluation/test_*.py` |
| Visualizer API | `tests/integration/visualizer/test_init_endpoint.py` |

---

## Evaluation tests

`tests/unit/evaluation/` — grouping, metrics, dashboard parser, benchmark writer.  
Do not require full 300-instance run in CI.

---

## Adding tests checklist

1. New public function → test file under matching `tests/unit/` mirror path
2. Neo4j mutation → mark `neo4j_required`, use `clean_db`
3. Parser edge case → add sample under `user_auth` fixture if needed
4. MCP contract change → update `test_server.py` / mocked tests + [mcp.md](mcp.md)

---

## Fixtures policy

- Prefer `tests/fixtures/user_auth/` for new integration scenarios
- Do not run `tests/fixtures/flask` test suite — dependency weight
