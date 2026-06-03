# Tech stack and dependencies

From `pyproject.toml`. Version **0.1.0**, Python **≥3.12**.

---

## Core runtime dependencies

| Package | Role in CodeGraph |
|---------|-------------------|
| `tree-sitter` + `tree-sitter-python` | Parse Python CST |
| `neo4j` | Graph database driver |
| `graphdatascience` | GDS client — projection + PageRank |
| `rank-bm25` | BM25 seed selection + baselines |
| `tiktoken` | Token counting for context budget |
| `mcp` | FastMCP server SDK |
| `python-dotenv` | Load `.env` for `NEO4J_PASSWORD` |
| `typer` + `rich` | CLI UX |
| `pyyaml` | `config.yaml` |
| `pathspec` | `.cgignore` / ignore patterns |
| `watchdog` | `codegraph watch` |

---

## Optional extras

| Extra | Packages | When |
|-------|----------|------|
| `dev` | pytest, pytest-asyncio | Development / CI |
| `bench` | datasets, gitpython | SWE-bench runner |
| `dashboard` | textual | `codegraph-bench-dashboard` |
| `visualizer` | fastapi, uvicorn | `codegraph visualize` |

---

## Frontend (separate `package.json`)

- **Vite** + **React** + **TypeScript**
- **D3** force simulation (`frontend/src/components/graph/`)
- Built with `npm run build`; served by Python visualizer

---

## External services

| Service | Requirement |
|---------|-------------|
| Neo4j 5.x | Bolt + Cypher storage |
| GDS plugin | Personalized PageRank |
| Git | `init` clone, evaluation cache, visualizer init |

No Redis, no vector DB, no cloud LLM for CodeGraph itself.

---

## Entry points

```toml
codegraph = "codegraph.cli.main:cli"
codegraph-mcp = "codegraph.mcp.server:main"
codegraph-bench-dashboard = "evaluation.dashboard.app:main"
```

---

## License

See root `LICENSE` file. Doc: [../license.md](../license.md) if present, else repo `LICENSE`.
