# CodeGraph

Graph-based context selection engine for AI coding agents.

CodeGraph parses a Python repository into a dependency graph (Neo4j), ranks code relevance with Personalized PageRank, and exposes the results through an MCP server. When you ask an AI assistant to edit your code, CodeGraph tells it exactly which files and functions to look at — not by guessing from embeddings, but by following the actual call and import graph.

## How it works

```
Your repo
  → tree-sitter parses every .py file
  → extracts Functions, Classes, Methods and their CALLS/IMPORTS/CONTAINS/INHERITS_FROM edges
  → stores the graph in Neo4j
  → when the AI asks "what's relevant to this task?", CodeGraph runs Personalized PageRank
    starting from the most likely seed nodes (matched by name + BM25 text)
  → returns ranked source code within a token budget
```

Results improve dramatically when the AI mentions specific entity names (e.g. `AuthService`, `validate_token`). Entity name matching is the strongest signal (0.6 weight), followed by BM25 text match (0.3).

## Use cases

**UC1 — Agent context** (primary): AI assistant calls `get_relevant_context` before editing code. Instead of guessing which files matter, the agent gets the top-k most structurally relevant entities within a token budget.

**UC2 — Explainability**: `codegraph explain "task"` shows which seed nodes PPR started from and the graph path to each result. Useful for debugging why a result was or wasn't returned.

**UC3 — Operations**: `codegraph analyze deps <EntityName>` traces callers and callees. `codegraph analyze dead-code` finds unreachable functions. `codegraph visualize` opens an interactive D3 force graph.

## Requirements

- Python 3.12+
- Neo4j 5.x with the **Graph Data Science (GDS)** plugin
  - Free: [Neo4j Desktop](https://neo4j.com/deployment-center/) (includes GDS)
  - Or: Neo4j Community Edition + manual GDS install

## Setup

```bash
# 1. Install
pip install -e .

# 2. Interactive setup — creates config.yaml and .env with Neo4j credentials
codegraph init

# 3. Register the MCP server with your AI assistant
codegraph install      # writes .mcp.json (Claude Code), claude.json (Claude Desktop), or .gemini/settings.json (Gemini CLI)

# 4. Index your project
codegraph rebuild

# 5. Verify everything is working
codegraph status
```

Restart your AI assistant after `codegraph install` to pick up the MCP server.

## MCP tools

The MCP server exposes two tools:

**`get_relevant_context`** — retrieve structurally relevant source code for a task.

```
task_description   plain-English description of what you're trying to do
mentioned_entities list of exact entity names the user mentioned, or null
top_k              max results (0 = server default ~15)
token_budget       max total tokens across results (0 = server default ~6000)
```

Returns JSON with a `summary` (result count, tokens used, visualizer URL) and `results[]` (entity name, type, file path, line range, relevance score, full source code).

**`query_dependencies`** — trace callers, callees, and imports for a named entity.

```
entity_name   name or qualified name (partial match accepted)
direction     "upstream", "downstream", or "both"
depth         1 (direct) or 2 (two-hop)
```

## CLI reference

```bash
codegraph init                              # Interactive setup wizard
codegraph install                           # Register MCP with Claude Code or Desktop
codegraph rebuild                           # Clear + re-parse + build graph
codegraph status                            # Project root, graph counts, last build, MCP registration
codegraph stats                             # Node/edge counts
codegraph doctor                            # Health checks with fix hints

codegraph query "add rate limiting"         # Run retrieval pipeline, print results
codegraph query "add rate limiting" --entity RateLimiter --compact
codegraph explain "add rate limiting"       # Show PPR seeds and reasoning paths
codegraph visualize                         # D3 force graph in browser (port 8474)

codegraph analyze deps AuthService          # All callers + callees
codegraph analyze deps AuthService --direction upstream
codegraph analyze dead-code                 # Unreachable functions

codegraph serve                             # Start MCP server (stdio) — used by install
codegraph watch                             # Incremental updates on file change
```

## Configuration

`codegraph init` generates `config.yaml`. The key sections:

```yaml
project_root: "."           # directory to index (relative to config.yaml)

neo4j:
  uri: "neo4j://localhost:7687"
  username: "neo4j"
  # password: set NEO4J_PASSWORD in .env — never stored here

ppr:
  damping_factor: 0.70      # tuned on SWE-bench Lite evaluation
  top_k: 30
  retrieval_mode: "uniform"

mcp:
  default_token_budget: 6000
  default_top_k: 15
```

Password is read from `NEO4J_PASSWORD` in `.env` (written by `codegraph init`) or from the environment.

## Troubleshooting

```bash
codegraph doctor    # checks config, credentials, Neo4j, GDS plugin, and graph index
```

Common issues:
- **Neo4j not reachable**: start Neo4j Desktop or run `neo4j start`, then check http://localhost:7474
- **GDS not found**: install the GDS plugin in Neo4j Desktop → your database → Plugins
- **Empty results**: run `codegraph rebuild` to index the project
- **Wrong results**: run `codegraph explain "your task"` to see which seeds PPR used

## Development

```bash
python -m pytest tests/unit/ -q    # 236 unit tests, no Neo4j needed
python -m pytest tests/ -v          # all tests (Neo4j tests skip if DB not running)
```

Architecture decisions are in `DECISIONS.md`. Read it before changing core algorithms.
