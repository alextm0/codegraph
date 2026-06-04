# Continuous integration

**Workflow:** `.github/workflows/ci.yml`

---

## Triggers

- Push to `main`
- Pull requests targeting `main`

---

## Job: test

| Step | Action |
|------|--------|
| Checkout | `actions/checkout@v4` |
| Python | 3.12 with pip cache |
| Install | `pip install -e ".[dev]"` |
| Test | `python -m pytest tests/ -v` |

**Timeout:** 15 minutes

---

## Neo4j in CI

GitHub Actions runners **do not** start Neo4j by default. Tests marked `neo4j_required` **skip** when bolt is unreachable — CI still passes on unit tests only.

To add Neo4j to CI in future:

- Service container with Neo4j + GDS, or
- Dedicated self-hosted runner

Document any change here and in [testing.md](testing.md).

---

## What CI does not run

- Full SWE-bench 300-instance evaluation (too slow; manual / separate pipeline)
- Frontend `npm test` (if added later, extend workflow)
- `mkdocs build` (no docs site generator)

---

## Local pre-push checklist

```bash
python -m pytest tests/unit/ -q
python -m ruff check .   # if project adopts ruff later
codegraph doctor         # manual, requires Neo4j
```

Match CI before opening PRs.
