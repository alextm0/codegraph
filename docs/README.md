# CodeGraph documentation (source of truth)

Plain Markdown for humans and **AI agents**. Read this tree before changing architecture, MCP tools, retrieval, evaluation claims, or thesis text.

**Not authoritative:** `docs/CodeGraphContext-Docs-From-Github/` (reference copy of a related project).

---

## Read first

| If you need… | Open |
|--------------|------|
| Repo tree and entry points | [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md) |
| End-to-end pipeline | [concepts/architecture.md](concepts/architecture.md) |
| Agent MCP rules | [guides/agent-workflows.md](guides/agent-workflows.md) + [AGENTS.md](../AGENTS.md) |
| Copy-paste commands | [QUICK_REFERENCE.md](QUICK_REFERENCE.md), [guides/cookbook.md](guides/cookbook.md) |
| Binding decisions | [DECISIONS.md](../DECISIONS.md) |

---

## Complete documentation index

### Root & cheatsheets

| Doc | Content |
|-----|---------|
| [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md) | Full repo directory map |
| [architecture.md](architecture.md) | One-page pipeline summary |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Commands + defaults |
| [MCP_TOOLS.md](MCP_TOOLS.md) | Two MCP tools quick ref |
| [UPDATING_DOCS.md](UPDATING_DOCS.md) | How to keep docs in sync with code |

### Getting started

| Doc | Content |
|-----|---------|
| [getting-started/prerequisites.md](getting-started/prerequisites.md) | Python, Neo4j, GDS, MCP clients |
| [getting-started/installation.md](getting-started/installation.md) | pip, init, install, rebuild |
| [getting-started/quickstart.md](getting-started/quickstart.md) | query, explain, visualize |
| [getting-started/mcp-setup.md](getting-started/mcp-setup.md) | Claude, Cursor, Gemini wiring |

### Core concepts (deep)

| Doc | Content |
|-----|---------|
| [concepts/architecture.md](concepts/architecture.md) | Stages, defaults, limitations, eval snapshot |
| [concepts/graph-model.md](concepts/graph-model.md) | Nodes, edges, identity, projection |
| [concepts/parser.md](concepts/parser.md) | tree-sitter, FileEntities, extractors |
| [concepts/call-resolution.md](concepts/call-resolution.md) | CALLS/IMPORTS linking, ambiguity rule |
| [concepts/neo4j-backend.md](concepts/neo4j-backend.md) | DB, GDS, constraints, Cypher layer |
| [concepts/how-it-works.md](concepts/how-it-works.md) | Ingest flow, rebuild, watch, auto-index |
| [concepts/retrieval-pipeline.md](concepts/retrieval-pipeline.md) | Seeds, IDF, PPR, token budget |
| [concepts/explainability.md](concepts/explainability.md) | explain, trace, contribution types |

### Guides

| Doc | Content |
|-----|---------|
| [guides/indexing.md](guides/indexing.md) | rebuild, excludes, .cgignore, watch |
| [guides/agent-workflows.md](guides/agent-workflows.md) | MCP order, anti-patterns |
| [guides/visualization.md](guides/visualization.md) | UI usage, dev mode |
| [guides/onboarding-codebase.md](guides/onboarding-codebase.md) | New repo checklist |
| [guides/development.md](guides/development.md) | Conventions, where to edit code |
| [guides/evaluation-harness.md](guides/evaluation-harness.md) | SWE-bench runner, ablations, results |
| [guides/cookbook.md](guides/cookbook.md) | Task recipes |
| [guides/demo-defense.md](guides/demo-defense.md) | Thesis live demo script |

### Reference

| Doc | Content |
|-----|---------|
| [reference/cli.md](reference/cli.md) | All CLI commands and flags |
| [reference/mcp.md](reference/mcp.md) | MCP schemas, errors, lifecycle |
| [reference/config.md](reference/config.md) | config.yaml keys |
| [reference/visualizer-api.md](reference/visualizer-api.md) | REST + WebSocket API |
| [reference/decisions.md](reference/decisions.md) | DEC-001 … DEC-010 index |
| [reference/troubleshooting.md](reference/troubleshooting.md) | doctor checks, fixes |
| [reference/module-map.md](reference/module-map.md) | `src/codegraph/` file roles |
| [reference/data-models.md](reference/data-models.md) | Dataclasses and DTOs |
| [reference/tech-stack.md](reference/tech-stack.md) | Dependencies and extras |
| [reference/testing.md](reference/testing.md) | pytest layout, neo4j_required |
| [reference/ci.md](reference/ci.md) | GitHub Actions |

### Thesis & research

| Doc | Content |
|-----|---------|
| [thesis/overview.md](thesis/overview.md) | Research goals ↔ code map |
| [thesis/evaluation.md](thesis/evaluation.md) | Metrics, iterations, citation rules |
| [thesis/related-work.md](thesis/related-work.md) | vs RAG, vs CodeGraphContext |

### Project

| [contributing.md](contributing.md) | PR / agent rules |
| [roadmap.md](roadmap.md) | Planned features |

---

## System in one paragraph

CodeGraph parses **Python** into a **Neo4j** graph (calls, imports, containment, inheritance), selects **seeds** from task text (entity names + BM25), runs **Personalized PageRank** (GDS, uniform restart, d=0.70, IDF-weighted edges), and returns ranked **source code** within a **token budget** via **two MCP tools** or the CLI/visualizer. Quality is measured on **SWE-bench Lite** file-level Recall@10 (~73–74% at best config).

---

## Internal notes (non-authoritative)

`docs/superpowers/` — planning/spec drafts for thesis tooling. Do not treat as system spec unless promoted into `concepts/` or `guides/`.

---

## External companions

| Artifact | Location |
|----------|----------|
| Decision log | `DECISIONS.md` |
| Agent short guide | `AGENTS.md` |
| Dev style | `CLAUDE.md` |
| LaTeX thesis | `thesis/` |
| Benchmark artifacts | `evaluation/results/` |
