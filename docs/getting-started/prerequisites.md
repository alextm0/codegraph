# Prerequisites

CodeGraph requires Python 3.12+, Neo4j 5.x with the Graph Data Science (GDS) plugin, and (for MCP) a compatible AI client.

## Python

- **Python 3.12+**
- Virtual environment recommended: `python -m venv .venv`

## Neo4j + GDS

CodeGraph stores the graph in **Neo4j** and runs Personalized PageRank via **GDS**.

**Easiest:** [Neo4j Desktop](https://neo4j.com/deployment-center/) — create a DBMS, enable the GDS plugin, start it. Default Bolt URI: `neo4j://localhost:7687`.

**Alternative:** Neo4j Community + manual GDS install per [Neo4j docs](https://neo4j.com/docs/graph-data-science/current/installation/).

Verify with:

```bash
codegraph doctor
```

## AI client (MCP)

Any MCP client that can run a local stdio server:

- Claude Code — `.mcp.json` via `codegraph install`
- Claude Desktop — `claude_desktop_config.json`
- Gemini CLI — `.gemini/settings.json`
- Cursor — MCP server config → `codegraph serve`

No API key is required for CodeGraph itself.

## Optional: visualizer development

```bash
cd frontend && npm install
codegraph visualize --dev
```

Next: [installation.md](installation.md)
