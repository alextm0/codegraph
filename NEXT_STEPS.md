# Next Steps, Testing Guide, and Possible Improvements

This document covers:
1. How to manually test everything built in Stage 5 (pipeline + MCP server)
2. What to do next
3. Potential improvements to consider later

---

## Part 1 — Testing What Was Built

### Prerequisites

You need Neo4j running locally before any of these tests will work.

Start Neo4j (Docker is the easiest way):

```bash
docker run \
  --name neo4j-codegraph \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/alex17toma02mihai04 \
  -e NEO4J_PLUGINS='["graph-data-science"]' \
  neo4j:5.25.1-community
```

Or if you already have Neo4j installed locally, just make sure it's running at `bolt://localhost:7687`.

Verify it's reachable:

```bash
python -c "
from src.graph.connection import load_config, create_driver, verify_connectivity
driver = create_driver(load_config('config.yaml'))
print('Connected:', verify_connectivity(driver))
"
```

---

### Test 1 — Run the full automated test suite

This runs all 238 tests. The ones that require Neo4j will run since the DB is up.

```bash
python -m pytest tests/ -v
```

Expected output: `238 passed`.

To run only the new Stage 5 tests:

```bash
python -m pytest tests/test_pipeline.py tests/test_mcp_server.py -v
```

Expected output: `44 passed`.

---

### Test 2 — Run the demo script end-to-end

The demo script (`scripts/demo_neo4j.py`) exercises the full pipeline against the
`user_auth` fixture and prints what each step does. This is the best way to
visually see that everything is wired together correctly.

```bash
python -m scripts.demo_neo4j
```

You should see output like:

```
INFO     demo_neo4j: === Step 1: Parse user_auth fixture with tree-sitter ===
INFO     demo_neo4j: Parsed 7 files
...
INFO     demo_neo4j: === Step 6: Seed node selection ===
INFO     demo_neo4j: Personalization vector (5 seeds):
INFO     demo_neo4j:   weight=0.4321  AuthService
...
INFO     demo_neo4j: === Step 7: IDF edge reweighting + PPR from seed vector ===
INFO     demo_neo4j: IDF weights applied to 27 edges
INFO     demo_neo4j: Top-10 PPR results from seed vector:
...
INFO     demo_neo4j: === Step 8: format_context (token budget=500) ===
INFO     demo_neo4j: Context items returned: 3
```

---

### Test 3 — Run the pipeline in a Python session

This lets you call the pipeline directly and inspect the output without the MCP layer.

```python
# Run with: python -c "..." or open a Python REPL in the project root

from pathlib import Path
from src.graph.connection import load_config, create_driver, load_full_config
from src.graph.ppr import create_gds_client
from src.graph.graph_builder import clear_database, build_graph
from src.parser.python_parser import create_parser, parse_directory
from src.retrieval.pipeline import run_retrieval_pipeline

# Point this at any Python project directory you want to index
PROJECT_DIR = "tests/fixtures/user_auth"

# Build the graph (only needed once, or after code changes)
config = load_config("config.yaml")
driver = create_driver(config)
clear_database(driver)
entities = parse_directory(PROJECT_DIR, create_parser())
build_graph(driver, entities)

# Run the pipeline
gds = create_gds_client(driver)
results = run_retrieval_pipeline(
    driver=driver,
    gds=gds,
    task_description="fix the user registration validation bug",
    project_root=PROJECT_DIR,
    mentioned_entities=["AuthService"],
    token_budget=3000,
)

for item in results:
    print(f"[{item.relevance_score:.4f}] {item.entity_name} ({item.token_count} tokens)")
    print(f"  File: {item.file_path}  lines {item.line_start}-{item.line_end}")
    print()
```

You should see several functions and methods from the `user_auth` fixture ranked
by relevance to the registration task, with their source code attached.

---

### Test 4 — Test the new graph query functions

Two new query functions were added to `src/graph/queries.py`. Test them directly:

```python
from src.graph.connection import load_config, create_driver
from src.graph.queries import query_entity_dependencies, get_most_connected_files

driver = create_driver(load_config("config.yaml"))

# What does 'register' call? (depth=1 = direct only)
deps = query_entity_dependencies(driver, "register", direction="downstream", depth=1)
for node in deps:
    print(f"  [{node.label}] {node.name}")

# What calls 'validate_email'? (upstream)
callers = query_entity_dependencies(driver, "validate_email", direction="upstream", depth=1)
for node in callers:
    print(f"  [{node.label}] {node.name}")

# Which files have the most entities?
top_files = get_most_connected_files(driver, limit=5)
for entry in top_files:
    print(f"  {entry['entity_count']} entities  {entry['file_path']}")
```

---

### Test 5 — Start the MCP server and inspect it with the MCP Inspector

The MCP Inspector is a browser-based tool for testing MCP servers without needing
Claude Desktop or Cursor.

Install and run it (requires Node.js):

```bash
npx @modelcontextprotocol/inspector python -m src.mcp_server
```

This opens a browser at `http://localhost:5173`. From there you can:

1. Click **"Connect"** to establish the STDIO connection.
2. Go to the **"Tools"** tab — you should see all three tools listed:
   - `get_relevant_context`
   - `query_dependencies`
   - `get_graph_stats`
3. Click **"get_graph_stats"** → **"Run Tool"** → see node/edge counts as JSON.
4. Click **"query_dependencies"** → fill in `entity_name: "AuthService"`,
   `direction: "both"`, `depth: 1` → run → see dependency list.
5. Click **"get_relevant_context"** → fill in
   `task_description: "fix the authentication bug"`,
   `mentioned_entities: ["AuthService"]` → run → see ranked source code.

Note: the graph must be built before using `get_relevant_context`. Use the demo
script (Test 2 above) or the pipeline session (Test 3) to build it first.

---

### Test 6 — Connect the MCP server to Claude Desktop

If you have Claude Desktop installed, you can add CodeGraph as a tool.

Edit `~/AppData/Roaming/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:\\Work\\Personal\\codegraph"
    }
  }
}
```

Or on Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`.

After restarting Claude Desktop, you should see the three CodeGraph tools
available in the tools panel. Try asking Claude:

> "Use the get_graph_stats tool to tell me about the codebase structure."

---

### Test 7 — Connect the MCP server to Claude Code (this CLI)

Add to your `~/.claude/settings.json` (or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:\\Work\\Personal\\codegraph"
    }
  }
}
```

Restart Claude Code and the three tools will appear in tool calls.

---

## Part 2 — What to Do Next

### Priority 1: Build a CLI for graph construction

✅ **DONE**: The unified CLI is now available as the `codegraph` command.

```bash
codegraph rebuild
codegraph stats
codegraph doctor
codegraph query "task description"
```

The CLI is implemented in `src/codegraph/cli/main.py`.
Entry points in `pyproject.toml`:
```toml
[project.scripts]
codegraph     = "codegraph.cli.main:cli"
codegraph-mcp = "codegraph.mcp.server:main"
```

---

### Priority 2: Index your own codebase

Once the CLI exists (or by calling the pipeline directly), try running CodeGraph
on a real project — not just the `user_auth` fixture. Good candidates:

- This project itself (`codegraph/`)
- A medium-sized open-source Python repo (~500–2000 entities)
- Your own work project

When you do, you'll discover real-world edge cases: files that fail to parse,
imports that don't resolve, very large classes, etc. Those findings should feed
back into improvements.

---

### Priority 3: Evaluation (Stage 6)

The docs describe `docs/09-evaluation.md` — benchmarking the pipeline against
SWE-bench or a similar dataset to measure whether the retrieved context is
actually useful for fixing bugs.

This is the most rigorous way to know if the system works well. It involves:
1. Taking a dataset of real bug reports + patches
2. Running the pipeline on each bug description
3. Checking whether the correct files/functions appear in the top-k results
4. Computing precision, recall, and MRR (Mean Reciprocal Rank)

This is a larger effort and should come after you've run the system on at least
one real codebase.

---

## Part 3 — Possible Improvements

These are not blockers. The system works correctly as-is. These are ideas for
when you return to this project and want to push quality further.

---

### Improvement 1: Cache the GDS projection across tool calls

**Current behavior:** `run_retrieval_pipeline` calls `ensure_graph_ready()` on
every invocation, which reapplies IDF weights and recreates the GDS projection
from scratch each time. This takes ~50ms for small graphs but could be noticeable
on larger ones.

**Improvement:** Store the projection in `ServerState` and only recreate it
when the underlying Neo4j graph has changed. One simple approach: hash the edge
count before and after — if it changed, rebuild; otherwise reuse.

**Why it's not done yet:** The added complexity of invalidation logic wasn't
worth it at current scale. See `DECISIONS.md` DEC-006 for the rationale.

---

### Improvement 2: Respect seed weights in PPR (weighted personalization)

**Current behavior:** `run_ppr_from_node_ids` passes all seed node IDs to GDS
equally. A node with `entity_match` weight 0.6 gets the same PPR teleportation
mass as a node with `bm25` weight 0.1. The `PersonalizationVector` captures the
intention, but GDS `pageRank.stream(sourceNodes=...)` doesn't support per-node
weights natively.

**Improvement:** Before projecting, set a `personalization_weight` property on
seed nodes in Neo4j, then use the `sourceNodeFilter` and a custom initial score
approach — or switch to a manual PPR implementation using the power iteration
method directly in Python, which gives full control over the teleportation
distribution.

**Trade-off:** More complex, and the quality gain may be small if seed selection
is already accurate. Worth A/B testing against evaluation results first.

---

### Improvement 3: Cache the BM25 index

**Current behavior:** `_bm25_search()` in `seed_selection.py` fetches all
`Function` and `Method` nodes from Neo4j and rebuilds the BM25 index in memory
on every `extract_seeds()` call.

**Improvement:** Cache the corpus in `ServerState` on first load, and
invalidate when the node count changes. This would reduce per-call latency
significantly for large graphs (10k+ functions).

---

### Improvement 4: Better token counting

**Current behavior:** `count_tokens()` in `post_processing.py` uses
`len(text.split())` — simple whitespace splitting. This under-counts by roughly
25% compared to actual LLM tokenizers (which split on subwords).

**Improvement:** Use `tiktoken` (OpenAI's tokenizer, free to use) for accurate
GPT-4 token counts, or use Anthropic's tokenizer for Claude-specific counts.

```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
def count_tokens(text: str) -> int:
    return len(enc.encode(text))
```

This is a dependency addition. Only worth doing if you find the budget is
consistently over- or under-shooting in practice.

---

### Improvement 5: Incremental graph updates

**Current behavior:** The only way to update the graph after code changes is to
call `clear_database()` followed by `build_graph()` — a full rebuild.

**Improvement:** Add a `update_graph(driver, changed_files)` function that:
1. Deletes existing nodes/edges for the changed files
2. Re-parses those files
3. Merges the new nodes/edges in

This is important for real-world use where you want the graph to stay in sync
as you edit code, without waiting for a full rebuild.

---

### Improvement 6: Multi-language support

**Current behavior:** Only Python files are parsed (via tree-sitter-python).

**Improvement:** tree-sitter supports 100+ languages. Adding JavaScript/TypeScript
support would require a new grammar (`tree-sitter-javascript`) and a new parser
module (`src/parser/javascript_parser.py`) that mirrors the structure of
`python_parser.py`.

The graph schema (File, Function, Class, Method, CALLS, IMPORTS) is
language-agnostic and would not need to change.

---

### Improvement 7: File-level seeds as fallback

**Current behavior:** If all three seed signals (entity match, BM25, current
file) produce zero seeds, the pipeline returns an empty result.

**Improvement:** Add a fourth fallback signal: pick the files that are most
frequently imported by other files in the graph ("hub files"). These are often
the most architecturally central and are a reasonable starting point when the
task is vague.

This would be a new signal in `seed_selection.py` with a very low weight
(e.g., 0.05) that only activates when all other signals produce no results.
