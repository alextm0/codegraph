# CodeGraph: Thesis Defense Concept Map

This document serves as the "Master Study Guide" for the CodeGraph thesis defense (July 1-3). It organizes the project into thematic pillars, covering both theoretical foundations and practical implementation details.

---

## 1. The Ingestion Pipeline (Source &rarr; Graph)
*The process of turning raw Python code into a structured property graph.*

### Core Concepts
*   **Tree-Sitter & CST:** How concrete syntax trees (CST) are used instead of abstract syntax trees (AST) to preserve precise line ranges and formatting for the agent.
*   **Entity Extraction:** The four-tier hierarchy: **File, Class, Function, Method**. Why this granularity? (Balance between noise and context).
*   **Static Call Resolution:**
    *   `resolve_caller`: How the system identifies the "parent" node of a call.
    *   `resolve_callee`: The logic for finding the target: **Import Map &rarr; Same-File &rarr; Global Unique**.
*   **Language Registry:** The design pattern used to allow future multi-language support (Registry pattern in `core/parser/registry.py`).

### Nuances & "Examiner Traps"
*   **The Ambiguity Rule:** Why does CodeGraph skip edges for ambiguous calls? (Reason: False edges in a graph create spurious PPR "shortcuts" that are more damaging than missing edges).
*   **Idempotency:** How `MERGE` and `UNWIND` in Cypher ensure that re-indexing the same file doesn't create duplicate nodes or orphaned relationships.

---

## 2. Graph Architecture (Neo4j & GDS)
*The storage and computation engine.*

### Core Concepts
*   **Schema Design:** The four relationship types: `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS_FROM`.
*   **GDS Projections:** What a "Projection" is in Neo4j. (An in-memory, optimized subgraph used specifically for running PageRank).
*   **Undirected Graphing:** Why the graph is projected as `UNDIRECTED` for PPR. (Reason: Retrieval needs to flow both "upstream" to callers and "downstream" to dependencies).

### Nuances & "Examiner Traps"
*   **In-Memory Lifecycle:** Every retrieval call drops and recreates the projection. Why? (Performance vs. Freshness: Ensuring `watch` mode changes are reflected immediately).
*   **Constraints:** The unique constraint on `qualified_name`. What happens if two files have the same path? (Path normalization logic).

---

## 3. The Retrieval Engine (The "Brain")
*How the system finds relevant code for a natural-language task.*

### Core Concepts
*   **Personalized PageRank (PPR):**
    *   **The Random Walk:** Explaining "damping factor" (0.70) as the probability of jumping back to a seed node.
    *   **PPR vs. Global PageRank:** Why "Personalization" is the key to task-specific relevance.
*   **Seed Selection:**
    *   **Entity Match (0.6):** Direct matches for symbols mentioned in the task.
    *   **BM25 (0.3):** Keyword-based matches for the task text.
    *   **Issue Hints (0.2):** Filenames found in the task description.
*   **IDF Edge Weighting:** How "Inverse Dependency Frequency" penalizes "hub" nodes (like `logger` or `utils.py`) so they don't wash out the results.

### Nuances & "Examiner Traps"
*   **Uniform vs. Weighted Restart:** Why does CodeGraph default to `uniform` restart mass across all seeds? (Avoids a single wrong seed node from dominating the entire retrieval).
*   **PPR vs. Embeddings:** The primary thesis argument: Why structural relationships (PPR) beat semantic similarity (Vector search) for complex codebase tasks.

---

## 4. Real-time Visualization & State
*The human-in-the-loop explainability layer.*

### Core Concepts
*   **WebSocket Pipeline:** How `codegraph watch` broadcasts events to the UI via the `/ws/status` endpoint.
*   **D3 Force-Graph Simulation:** The physics engine behind the graph layout (Charge, Link Strength, Collision Detection).
*   **Reasoning Paths:** How the UI "traces" the shortest path from a Seed node to a Result node to explain why the result was picked.

### Nuances & "Examiner Traps"
*   **State Sync:** How the frontend keeps 10,000+ nodes in React state without lagging. (Selective rendering and WebGL-based vs SVG rendering decisions).
*   **Why WebSockets?** Why not simple polling? (Real-time feedback during large `rebuild` operations).

---

## 5. Scientific Evaluation (Verification)
*Proving that the system actually works.*

### Core Concepts
*   **SWE-bench Lite:** The dataset of 300 real-world GitHub issues used as the "Gold Standard."
*   **Recall@10 (74.0%):** The primary metric. Why is Recall more important than Precision for retrieval? (You can't fix a bug if you don't even see the file).
*   **Ablation Studies:** The "What if?" experiments. What happens if you remove `INHERITS_FROM` edges? (Data shows which relationships contribute most to finding bugs).

### Nuances & "Examiner Traps"
*   **The Reachability Ceiling:** ~78 instances in the benchmark had 0% recall. Why? (Static analysis limits: if there is no path in the graph from the seed to the gold file, PPR can never find it).
*   **Baselines:** How much better is CodeGraph than a simple `grep` or keyword search? (The 24.3% gain over BM25).

---

## 6. The Agent Interface (MCP)
*How the tool is actually used by AI.*

### Core Concepts
*   **Model Context Protocol (MCP):** The open standard for connecting AI to tools.
*   **Token Budgets:** Why we limit retrieval to 6,000 tokens. (Model context limits and cost efficiency).
*   **Two-Tool Minimalism:** Why only `get_relevant_context` and `query_dependencies`? (Reducing "Tool Choice Paralysis" for the agent).

### Nuances & "Examiner Traps"
*   **Background Indexing:** What happens if the agent calls a tool on an empty graph? (The silent auto-rebuild logic).
*   **Trust Signals:** How `seeds[]` and `explanations` in the MCP output help the agent "verify" its own retrieval.
