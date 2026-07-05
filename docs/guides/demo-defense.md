# Thesis Defense Demo Script

This document outlines the step-by-step narrative and technical script for the CodeGraph thesis live demo. The flow builds the audience's understanding progressively: starting from raw data ingestion (CLI), showing the core value proposition (AI Agents via MCP), and ending with deep explainability (React Visualizer).

---

## Preparation (Pre-Demo)

1. **Neo4j Database**: Ensure Neo4j 5.x is running in the background with the GDS plugin enabled.
2. **Terminal**: Have a terminal open at the `codegraph` project root.
3. **Claude Desktop**: Installed, with CodeGraph MCP configured (`codegraph install`), and restarted.
4. **Browser**: Have an empty tab ready for `localhost:8474`.

*Note: Ensure your `config.yaml` has `exclude_seed_paths: ["tests/", "test_"]` so the queries prioritize core parsing logic over unit tests.*

---

## Act 1: The Foundation & Ingestion (CLI)

**Goal:** Demonstrate how easy it is to bring a codebase into CodeGraph and interact with it natively from the terminal.

1. **Overview of Capabilities**
   - **Command:** `codegraph --help`
   - *Talking Point:* Briefly show the suite of tools available to the developer (init, rebuild, analyze, explain, visualize).

2. **Indexing a Repository**
   - **Command:** `codegraph init https://github.com/alextm0/codegraph`
   - *Talking Point:* Explain that CodeGraph can seamlessly ingest a remote repository. (You can also run `codegraph init .` if preferred for speed).
   - **Command:** `codegraph rebuild`
   - *Talking Point:* Point out the logs as it parses ASTs via tree-sitter. Explain that it's creating UNWIND+MERGE Neo4j nodes (Functions, Classes, Methods) and edges (CALLS, IMPORTS, CONTAINS).
   - *Result Check:* Highlight the final node/edge count (e.g., ~1356 nodes, ~2853 edges) so the audience grasps the scale.

3. **Terminal Retrieval & Explainability**
   - **Command:** `codegraph explain "How are Python entities like Functions and Classes extracted into FileEntities?"`
   - *Talking Point:* Show how the CLI surfaces seed nodes (like `FileEntities` and `parse_file` via BM25 and Entity matches) and runs Personalized PageRank (PPR) to return top-scored files (`src/codegraph/core/parser`). 
   - *Why this works:* This specific query yields high-quality structural seeds (like `_build_entity_lookup` and `extract_functions`), accurately proving that CodeGraph understands its own parser.

---

## Act 2: The Core Value Proposition (MCP & AI Agents)

**Goal:** Show CodeGraph in action inside a real AI workflow, proving that structural context improves LLM responses.

1. **Triggering the Tool**
   - Open **Claude Desktop**.
   - **Prompt:** *"I'm exploring the CodeGraph codebase. Use your CodeGraph tools to find relevant context and explain how the abstract syntax tree is parsed to create graph nodes and edges."*
   
2. **Observing the Integration**
   - Show Claude automatically invoking the `get_relevant_context` tool.
   - *Talking Point:* Emphasize that the AI doesn't rely on generic RAG/embeddings. It uses the exact same seed-selection and PPR pipeline we just saw in the CLI.

3. **The Result**
   - Review Claude's response.
   - *Talking Point:* Highlight how the agent successfully pinpointed structural components (e.g., `PythonParser`, `GraphBuilder`) without hallucinating, thanks to the exact structural context provided by the MCP server.

---

## Act 3: Explainability & Deep Dive (React Visualizer)

**Goal:** "Look under the hood" to show exactly *why* CodeGraph retrieved that context, emphasizing the transparency of the thesis project.

1. **Launching the UI**
   - **Command:** `codegraph visualize`
   - Open `http://localhost:8474` in the browser.

2. **UI Walkthrough**
   - **Repository Management:** Show the UI dropdown for switching between indexed repositories, demonstrating multi-repo support.
   - **File Explorer:** Demonstrate viewing raw repository files directly within the application, providing immediate local context without needing an IDE.

3. **Visual Retrieval Pipeline**
   - **Querying:** Type the exact same query in the panel: *"How are Python entities like Functions and Classes extracted into FileEntities?"*
   - **Seed Nodes:** Point out the list of initial seeds extracted from the query.
   - **PPR Scores & Results:** Show the ranked sidebar. 
   - *Talking Point:* Note that the PPR scores here identically match the CLI and MCP outputs—proving the consistency of the shared retrieval core.
   
4. **Graph Interaction**
   - **Force Graph:** Show the highlighted paths propagating out from the seeds.
   - **Node Inspection:** Click on a high-ranking node (like `PythonParser.parse` or `FileEntities`) to show how the UI fetches the source code snippet and file context on the side panel.

---

## Summary for the Audience
Conclude the demo by summarizing the pipeline: **Python Source → Neo4j Graph → Personalized PageRank → MCP/CLI/Visualizer**. Emphasize that CodeGraph is a unified structural retrieval core accessible across all developer surfaces.

## Fallbacks

| Problem | Action |
|---------|--------|
| Empty graph | `codegraph rebuild` |
| MCP missing | `codegraph install` + restart IDE |
| GDS error | Neo4j Desktop → Plugins |
| Slow clone | Run `codegraph init .` instead of the Github URL |
