# Onboarding a new codebase

Checklist for indexing a repository you have not used with CodeGraph before.

---

## 1. Prerequisites

- Neo4j + GDS running
- Python 3.12+ venv with `pip install -e .`

See [../getting-started/prerequisites.md](../getting-started/prerequisites.md).

---

## 2. Point CodeGraph at the repo

**Option A — existing clone:**

```bash
cd /path/to/repo
codegraph init    # writes config.yaml + .env here or in parent
```

Set `project_root` in `config.yaml` to the repo root (`.` or absolute path).

**Option B — clone via init:**

```bash
codegraph init https://github.com/org/repo
```

---

## 3. Tune excludes

Add patterns for vendored code, generated files, huge fixtures:

```yaml
exclude_patterns:
  - .venv
  - node_modules
  - "**/migrations/**"
```

Optional `.cgignore` for pathspec rules.

---

## 4. Index and verify

```bash
codegraph rebuild
codegraph stats
codegraph doctor
```

Sanity query with a known module:

```bash
codegraph query "main entry point" --compact
```

---

## 5. MCP for the team

```bash
codegraph install
```

Commit `.mcp.json` (Claude Code) if the team shares MCP config. **Do not commit** `.env` or passwords.

---

## 6. Calibrate retrieval

- Run a task similar to real issues: `codegraph query "..." -e KnownClass`
- If results are poor: `codegraph explain "..."` and adjust `mentioned_entities` in agent prompts
- Consider `seed_selection.exclude_seed_paths` if test files pollute BM25 seeds

---

## 7. Thesis / evaluation repos

SWE-bench Lite repos are large. Use evaluation harness under project scripts (not duplicated here). Metrics doc: [../thesis/evaluation.md](../thesis/evaluation.md).

For Flask-sized fixtures, `tests/fixtures/` is used in unit tests — do not confuse with production `project_root`.
