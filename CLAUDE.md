# CLAUDE.md

## Project

**CodeGraph** — Structural context retrieval for AI coding agents.

CodeGraph achieves **74.0% Recall@10**, delivering a **24.3 percentage point gain** over standard BM25 lexical search. It is a Python-first, agent-oriented retrieval system that prioritizes structurally precise context over broad, shallow search.

## Mental Model

- **Indexing Path (Offline)**: Python → tree-sitter → Neo4j structural graph.
- **Retrieval Path (Online)**: Task → seeds → Personalized PageRank → ranked context snippets.

## Trust & Transparency

1. **Seed Provenance**: Every retrieved entity explicitly identifies the "seeds" (entity names or text matches) that triggered its selection.
2. **Traceable Paths**: The `explain` interface reveals the structural relationship between the task and the retrieved code.
3. **Shared Retrieval Core**: Identical ranking logic powers the CLI, MCP, and visualizer.

## Architecture

```
Indexing Path: Source code → tree-sitter parse → entity extraction → graph build
Retrieval Path: User Task → seed selection → PPR → context formatting → delivery
```

Detailed documentation for each component is in `docs/` — start at `docs/README.md` (agent source of truth).
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
├── docs/             ← README.md, concepts/, guides/, reference/, thesis/
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
- Frozen dataclasses over Pydantic for entity models.
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
