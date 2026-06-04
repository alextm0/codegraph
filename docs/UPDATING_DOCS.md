# Keeping documentation accurate

Documentation under `docs/` is the **source of truth for agentic development** (Cursor, Claude, Gemini). No MkDocs or site generator — plain Markdown only.

---

## Structure

```
docs/
├── README.md                 # Start here — doc map
├── architecture.md           # Short summary + links
├── QUICK_REFERENCE.md
├── MCP_TOOLS.md
├── UPDATING_DOCS.md
├── getting-started/
├── concepts/
├── guides/
├── reference/
├── concepts/          # architecture, parser, resolution, neo4j, retrieval, explainability
├── guides/            # indexing, agents, viz, eval harness, cookbook, demo
├── reference/         # cli, mcp, config, api, testing, ci, data-models, tech-stack
├── thesis/
├── PROJECT_LAYOUT.md
├── contributing.md
├── roadmap.md
└── CodeGraphContext-Docs-From-Github/   # reference only — do not edit for CodeGraph
```

Repo root companions: `AGENTS.md`, `CLAUDE.md`, `DECISIONS.md`.

---

## When you change code, update docs

| Change | Update |
|--------|--------|
| CLI command / flag (e.g. `find`) | `reference/cli.md`, `QUICK_REFERENCE.md`, `guides/cookbook.md` |
| MCP parameters / JSON | `reference/mcp.md`, `MCP_TOOLS.md`, `AGENTS.md` |
| config.yaml keys | `reference/config.md` |
| Algorithm / defaults | `DECISIONS.md`, `concepts/retrieval-pipeline.md`, `reference/decisions.md` |
| New module | `reference/module-map.md` |
| Evaluation metrics | `thesis/evaluation.md`, `thesis/chapters/chapter5_*.tex`; benchmark claims require `evaluation/results/iteration_2_top_30/summary.json` or a new full-run `summary.json` |
| New binding choice | `DECISIONS.md` + row in `reference/decisions.md` |

---

## Rules for agents

- Prefer `docs/` over guessing from CodeGraphContext reference copy
- If docs and code disagree, **code wins** until docs are fixed in the same PR
- Never cite CGC behavior as CodeGraph behavior

---

## Thesis

LaTeX lives in `thesis/`. Mirror metrics in `docs/thesis/evaluation.md` when chapter 5 changes.
