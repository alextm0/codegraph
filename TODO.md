# CodeGraph — TODO & Future Ideas

## Thesis (deadline: May 25 paper, July defense)

### Deep system understanding (do this before writing Chapters 4–7)
The system was built with heavy agentic/vibe coding. Before writing or defending, you need to own every design decision at a level where you can answer "why did you do it this way?" without hesitation. Go module by module:

- [ ] **Parsing pipeline** — `core/parser/python_parser.py`: how does tree-sitter extract entities? what are the edge cases (decorators, nested functions, dynamic imports)? what gets silently dropped?
- [ ] **Graph construction** — `core/graph/graph_builder.py`: how are CALLS vs IMPORTS vs CONTAINS vs INHERITS_FROM edges decided? why UNWIND+MERGE? what does the graph look like for a circular import?
- [ ] **PPR algorithm** — `core/graph/ppr.py`: what does `damping_factor=0.70` actually mean mathematically? why UNDIRECTED projection? why uniform mode beats weighted? be able to derive the PPR formula on a whiteboard
- [ ] **Seed selection** — `core/retrieval/seed_selection.py`: exactly how are the 3 signals (entity match 0.6, BM25 0.3, current_file 0.1) combined? what is the fallback chain when entity match returns nothing?
- [ ] **Post-processing** — `core/retrieval/post_processing.py`: what does IDF weighting do on top of PPR scores? why is it needed? what would the results look like without it?
- [ ] **MCP server lifecycle** — `mcp/server.py`: how does the FastMCP lifespan pattern work? what happens to the Neo4j connection when the agent disconnects? what fails if Neo4j is down at startup?
- [ ] **Token budget** — how is the budget enforced? is it exact or approximate? what gets cut when the budget is hit?

For each module: read the code, trace one real query end-to-end through it, then write 2–3 sentences in your own words explaining what it does and why. That's your Chapter 4 material.

### Chapters
- [ ] Chapter 4 — Implementation: walk through build pipeline stage by stage; code is the evidence
- [ ] Chapter 5 — Evaluation: tell the 42%→74% story; bimodal distribution + seed quality findings are the core; report iter 3 negative result honestly
- [ ] Chapter 6 — Discussion & Limitations: zero-recall cases, Python-only, no semantic understanding; iter 3 as methodological lesson
- [ ] Chapter 7 — Conclusion: restate trajectory, key finding, one paragraph future work
- [ ] Review pass across all chapters for consistency (May 20–25)

---

## Demo polish (before July defense)

- [ ] `codegraph install` — one command writes `.mcp.json` or updates `~/.claude.json`, detects Claude Code vs Desktop, confirms server is reachable (replaces manual `.mcp.json` setup)
- [ ] Stability pass — run the full demo flow on a fresh repo, fix whatever breaks
- [ ] Re-index against a clean example repo before any live demo (current graph is indexed against benchmark cache)

---

## Tooling quality — make it actually usable (priority before any algorithm work)

### Week 1 — Frictionless setup
- [ ] `codegraph install` wizard — finish it; writes `.mcp.json` or `~/.claude.json`, detects Claude Code vs Desktop, confirms server reachable
- [ ] Improve `codegraph init` — interactive Neo4j setup walkthrough, not just config file generation
- [ ] `codegraph doctor` should fix, not just diagnose — "Neo4j not running, start it? [Y/n]"

### Week 2 — Harden failure paths
- [ ] Audit every error surface (MCP tool errors, CLI errors, empty graph) — every failure should tell the user exactly what to do next; no stack traces reaching the user
- [ ] `codegraph status` command — what repo is indexed, node/edge counts, when last built, whether MCP server is registered; single command for "what is the current state"
- [ ] Empty graph detection in MCP — return actionable hint ("run codegraph rebuild") not a bare empty result

### Week 3 — Documentation
- [ ] **Update CLAUDE.md** — reflect current state: 2 MCP tools, simplified CLI (~10 commands), removed surfaces (no find/complexity/pipeline/comparison/explorer); update MCP tools section, commands list, and project structure; commit and push (CLAUDE.md is gitignored — check first)
- [ ] **Update AGENTS.md** — same as CLAUDE.md; ensure any AI agent picking up this repo gets an accurate picture of what exists
- [ ] **Rewrite README** — match current state: 2 MCP tools, ~10 CLI commands, actual setup flow (currently describes old 10-tool surface); add "how it works" section (one page a skeptical developer can read in 3 minutes); frame around 3 use cases: UC1 agent context, UC2 explainability, UC3 operations; commit and push
- [ ] Link visualizer from MCP response summary — when agent gets results, include the visualizer URL so a developer can debug/verify via `codegraph visualize`

### If time allows — robustness
- [ ] Edge case testing: empty repos, repos with syntax errors, very large repos, circular imports
- [ ] Happy path tests exist; failure mode coverage is thin

---

## Signals & algorithm improvements (explore after tooling is clean)

- [ ] **Git co-change edges** — files committed together frequently are semantically coupled even when structurally unrelated; parse `git log` to add co-change edges to the graph; directly attacks the "structurally unrelated but semantically coupled" failure mode; well-researched (MSR literature); one weekend to implement; strong thesis evaluation candidate
- [ ] **Docstring/comment parallel channel** — BM25 over docstrings in parallel with PPR over structure; catches queries like "find rate limiting logic" where the function name gives no signal; doesn't change core algorithm
- [ ] **Test file awareness** — `include_tests: true` param on `get_relevant_context`; tests are often the best usage documentation; currently excluded entirely
- [ ] **Learned edge weights** — train weighting on SWE-bench results instead of manual tuning; small training set is enough; revisits iter 3 finding without manual weight guessing
- [ ] **Scope-aware chunking** — return minimal enclosing AST scope relevant to query instead of full function body; reduces token waste on large functions; requires query-time AST analysis
- [ ] **Query decomposition** — for complex queries, expand into sub-queries before running PPR ("implement OAuth login" → "session creation", "token validation", "redirect handling") → merge results; uses MCP back-and-forth protocol
- [ ] **Repo-level memory** — persistent per-repo index tracking which entities retrieved together successfully, which queries led to good responses; makes repeated queries on same repo better over time

---

## Tier 1 — Remove setup barriers (highest real-world impact)

- [ ] **Embedded graph DB (Kuzu)** — swap Neo4j for [Kuzu](https://kuzudb.com/); embeddable, zero server setup, runs in-process, stores state in a local file; PPR ports directly; drops the biggest adoption barrier from "install + configure Neo4j" to just `pip install codegraph`
- [ ] **Auto-index on first use** — if graph is empty when `get_relevant_context` is called, detect it and run indexing automatically; fall back to BM25-only while graph builds in background
- [ ] **`codegraph install` wizard** — see Demo polish above; same item

---

## Tier 2 — Better results (high impact, higher effort)

- [ ] **Multi-language support** — TypeScript/JS first (tree-sitter-javascript, call graph extraction follows same pattern); Python-only is a hard ceiling on real-world usefulness
- [ ] **Incremental indexing** — file-level diffing, partial graph updates; makes the index feel live instead of stale; `watch` exists but `rebuild` is still the reliable path
- [ ] **Embedding-based seed signal** — add a 4th seed signal using a local embedding model (e.g. `nomic-embed-text` via Ollama) to improve seed quality for queries where entity names don't match the task description; directly attacks the 58% zero-recall cases

---

## Tier 3 — Trust & transparency (medium impact, low effort)

- [ ] **Reasoning field in MCP response** — per result: why it was ranked ("seed: `AuthService` → 2 hops via CALLS → this function"); agents and users trust results they can explain
- [ ] **Staleness warnings** — if graph is >24h old or git has uncommitted changes, include `stale: true` + hint in `get_relevant_context` summary
- [ ] **Seed confidence score** — include `seed_confidence` in summary; low score (BM25-only, no entity matches) signals to the agent to be skeptical

---

## Previously completed ✓

- [x] Stages 1–5: parsing, graph, retrieval, MCP, CLI
- [x] Evaluation iterations 1–3: 42% → 74% R@10
- [x] `codegraph explain` command
- [x] `codegraph index <github-url>`
- [x] Visualizer label fix
- [x] MCP pruned to 2 tools (`get_relevant_context`, `query_dependencies`)
- [x] CLI simplified (removed `find`, `analyze complexity`, duplicate analyze commands)
- [x] Frontend simplified (removed Pipeline/Comparison views, Explorer tab)
- [x] Tool annotations (`readOnlyHint`, `idempotentHint`) + rewritten tool contracts
- [x] `.mcp.json` project config for Claude Code
