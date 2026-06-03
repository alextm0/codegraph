# CodeGraph quick reference

## First-time setup

```bash
pip install -e .
codegraph init
codegraph install          # register MCP with Claude / Gemini
codegraph rebuild
codegraph doctor
```

## Daily commands

| Goal | Command |
|------|---------|
| Re-index after big changes | `codegraph rebuild` |
| Health check | `codegraph doctor` |
| Graph size | `codegraph stats` |
| Project + MCP status | `codegraph status` |
| Retrieve context (CLI) | `codegraph query "task" --entity AuthService` |
| Debug ranking | `codegraph explain "task"` |
| Callers / callees | `codegraph analyze deps EntityName --direction upstream` |
| Dead code | `codegraph analyze dead-code` |
| Visualizer | `codegraph visualize` |
| Live updates | `codegraph watch` |

## MCP tools (exactly 2)

1. **`get_relevant_context`** — PPR-ranked source for a task (call first).
2. **`query_dependencies`** — upstream/downstream/both, depth 1 or 2.

## PPR defaults (do not change without benchmarking)

- `damping_factor`: **0.70**
- `top_k`: **30**
- `retrieval_mode`: **uniform**
- Seed weights: entity **0.6**, BM25 **0.3**

## Config essentials

- `project_root` — what gets indexed
- `NEO4J_PASSWORD` in `.env` — never in `config.yaml`
- `exclude_patterns` / `.cgignore` — skip tests, vendored code

## When things break

```bash
codegraph doctor
codegraph rebuild
```

Full docs: run `mkdocs serve` from `docs/` or read `docs/docs/index.md`.
