# CodeGraph Thesis Live Demo Flow

This document outlines the step-by-step narrative and technical script for the CodeGraph thesis live demo. The flow is designed to progressively build the audience's understanding of the system: starting from raw data ingestion (CLI), showing the core value proposition (AI Agents via MCP), and ending with deep explainability (React Visualizer).

## Prerequisites & Setup (Pre-Demo)
- **Neo4j Database**: Ensure Neo4j 5.x is running in the background with the GDS (Graph Data Science) plugin enabled. Briefly mention this at the start of the demo so the audience understands the backend architecture.
- **Claude Desktop**: Installed and restarted with CodeGraph MCP configured.
- **Terminal & Browser**: Ready and clean.

---

## Act 1: The Foundation & Ingestion (CLI)

**Goal:** Demonstrate how easy it is to bring a codebase into CodeGraph and interact with it natively from the terminal.

1. **Overview of Capabilities**
   - Command: `codegraph --help`
   - *Talking Point:* Briefly show the suite of tools available to the developer (init, rebuild, analyze, explain, visualize, etc.).

2. **Indexing a Repository**
   - Command: `codegraph init https://github.com/pallets/flask`
   - *Talking Point:* Explain that CodeGraph can seamlessly ingest a remote repository via its Github URL.
   - Command: `codegraph rebuild`
   - *Talking Point:* Point out the logs as it parses ASTs via tree-sitter and creates UNWIND+MERGE Neo4j nodes (Functions, Classes, Methods) and edges (CALLS, IMPORTS, CONTAINS). Highlight the final node/edge count so the audience grasps the scale.

3. **Terminal Retrieval**
   - Command: `codegraph explain "How does routing work?"`
   - *Talking Point:* Show how the CLI surfaces seed nodes (BM25 vs. Entity matches) and runs Personalized PageRank (PPR) to return top-scored files and functions directly in the terminal for developer speed.

---

## Act 2: The Core Value Proposition (MCP & AI Agents)

**Goal:** Show CodeGraph in action inside a real AI workflow, proving that structural context improves LLM responses.

1. **Triggering the Tool**
   - Open **Claude Desktop** (or Cursor).
   - Prompt: *"I'm exploring the Flask codebase. Use your CodeGraph tools to find relevant context and explain how routing works and how I would add a custom route."*
   
2. **Observing the Integration**
   - Show Claude automatically invoking the `get_relevant_context` tool.
   - *Talking Point:* Explain that the AI doesn't rely on generic RAG/embeddings. It uses the exact same seed-selection and PPR pipeline we just saw in the CLI.

3. **The Result**
   - Review Claude's response.
   - *Talking Point:* Highlight how the agent successfully pinpointed structural components like `Blueprint` or `dispatch_request` without hallucinating, thanks to the exact structural context provided by the MCP server.

---

## Act 3: Explainability & Deep Dive (React Visualizer)

**Goal:** "Look under the hood" to show exactly *why* CodeGraph retrieved that context, emphasizing the transparency of the thesis project.

1. **Launching the UI**
   - Command: `codegraph visualize`
   - Open `http://localhost:8474` in the browser.

2. **UI Walkthrough**
   - **Repository Management:** Show the UI dropdown for switching between indexed repositories, demonstrating multi-repo support.
   - **File Explorer:** Demonstrate viewing raw repository files directly within the application, providing immediate local context without needing an IDE.

3. **Visual Retrieval Pipeline**
   - **Querying:** Type the exact same query in the panel: *"How does routing work?"*
   - **Seed Nodes:** Point out the list of initial seeds extracted from the query.
   - **PPR Scores & Results:** Show the ranked sidebar. 
   - *Talking Point:* Note that the PPR scores here identically match the CLI and MCP outputs.
   
4. **Graph Interaction**
   - **Force Graph:** Show the highlighted paths propagating out from the seeds.
   - **Node Inspection:** Click on a high-ranking node (e.g., `dispatch_request` or `Flask.route`) to show how the UI fetches the source code snippet and file context on the side panel.

---

## Summary for the Audience
Conclude the demo by summarizing the pipeline: **Python Source → Neo4j Graph → Personalized PageRank → MCP/CLI/Visualizer**. Emphasize that CodeGraph is a unified structural retrieval core accessible across all developer surfaces.
