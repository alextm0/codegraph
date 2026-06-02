# CLAUDE.md

## Project

**CodeGraph** — Graph-based context selection engine for AI coding agents.

Parses Python repositories into dependency graphs (Neo4j), ranks code relevance using Personalized PageRank, and exposes results via an MCP server that any AI agent can plug into.

## Architecture

```
Source code → tree-sitter parsing → entity extraction → import/call resolution
→ Neo4j graph → Personalized PageRank → post-processing → MCP server → AI agent
```

Detailed documentation for each component is in `docs/`.
All technical decisions are recorded in `DECISIONS.md`.

## Tech Stack

- **Python 3.12+**
- **tree-sitter** + tree-sitter-python — AST parsing
- **neo4j** Python driver + **graphdatascience** — graph database + PPR algorithm
- **mcp** Python SDK — MCP server
- **rank-bm25** — BM25 baseline for evaluation and seed selection
- **pytest** — testing
- **pyyaml** — configuration
- **pathspec** — .gitignore parsing

## Project Structure

```
codegraph/
├── docs/             ← architecture.md (tracked)
├── DECISIONS.md      ← binding technical decisions
├── src/codegraph/
│   ├── cli/commands/ ← CLI command implementations
│   ├── core/         ← parsing, graph, retrieval logic
│   ├── mcp/          ← MCP server implementation
│   └── utils/        ← shared helpers
├── tests/
│   ├── fixtures/     ← user_auth (main), flask
│   ├── unit/         ← per-module unit tests
│   └── integration/  ← end-to-end and server tests
└── config.yaml       ← global configuration
```

## Code Guidelines

**Style:**
- Type hints on all function signatures. No exceptions.
- Docstrings on all public functions. One-liner is fine if the function is obvious.
- Frozen dataclasses over Pydantic for entity models (DEC-002).
- No function longer than 50 lines. If it's longer, split it.
- Name things clearly. `resolve_import()` not `process()`. `ppr_results` not `data`.

**Modules:**
- Core logic is in `src/codegraph/core/`.
- `codegraph.core.parser` handles tree-sitter AST extraction.
- `codegraph.core.graph` handles Neo4j and GDS/PPR operations.
- `codegraph.core.retrieval` contains the retrieval pipeline.
- Use dependency injection (pass dependencies as arguments) not global state.

**MCP Server:**
Exposes exactly **2 tools**:
1. `get_relevant_context`: Main entry point for context retrieval. Returns ranked source code entities for a task description using PPR.
2. `query_dependencies`: Upstream/downstream dependency analysis for a named entity.

There is no `get_graph_stats`, `find_dead_code`, or `execute_cypher_query` MCP tool — those are CLI-only commands.

**Testing:**
- Every module gets a test file.
- Use the `tests/fixtures/user_auth/` for integration tests.
- Test edge cases: empty files, files with syntax errors, circular imports.

## Common Commands

**Setup:**
```bash
pip install -e .
codegraph init         # Interactive wizard: Neo4j credentials, project root, config.yaml
codegraph install      # Register MCP server with Claude Code, Claude Desktop, or Gemini CLI
```

**Daily use:**
```bash
codegraph rebuild      # Index codebase into Neo4j
codegraph status       # Show project, graph counts, last build, MCP registration
codegraph stats        # Show graph node/edge counts
codegraph doctor       # Check Neo4j/GDS/config health with fix hints
codegraph query "task description" --entities AuthService
codegraph explain "task description"   # Show seeds + PPR reasoning paths
```

**Visualizer:**
```bash
codegraph visualize    # Open D3 force graph in browser (port 8474)
```

**Analysis:**
```bash
codegraph analyze deps <EntityName> --direction upstream
codegraph analyze dead-code
```

**Testing:**
```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/integration/mcp/test_server.py -v
```

**Performance:**
- Don't optimize prematurely. Get it correct first.
- Use batched Neo4j operations (UNWIND), never individual CREATEs in a loop.
- Tree-sitter parsing is already fast. Don't parallelize unless parsing takes >10 seconds.

## PPR Defaults (iter-2 tuned)

- `damping_factor`: 0.70
- `top_k`: 30
- `retrieval_mode`: "uniform"

These are the correct defaults. Do not use 0.85/20 — those are the old pre-tuning values.

## Decision Log

All technical decisions are recorded in `DECISIONS.md` at the project root.

**Rules for AI assistants:**

1. **Before suggesting an alternative approach**, check `DECISIONS.md`. If the topic is already decided (Status: ACTIVE), follow the existing decision. Do not suggest alternatives unless explicitly asked.

2. **When a decision is made during a session**, ask: "Should I add this to DECISIONS.md?" Then append using the template in that file. Use the next sequential number.

3. **When implementation contradicts a decision**, flag it: "This conflicts with DEC-XXXX. Follow existing decision or update it?"

4. **Never silently override a decision.**

5. **When starting a new module**, read `DECISIONS.md` first to understand existing constraints.
