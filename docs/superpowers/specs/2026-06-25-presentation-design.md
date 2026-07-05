# CodeGraph Conference Presentation Design

## Narrative Flow
The presentation follows a "Problem -> Architectural Solution -> Empirical Proof -> Practical Ecosystem" arc. It emphasizes the contrarian view that deterministic graph propagation outperforms text-centric retrieval for coding agents.

## Slide-by-Slide Plan

### Slide 1: Title
*   **Goal:** Introduce the research topic.
*   **Visual:** Clean dark navy Beamer template.
*   **Message:** Welcome. We are presenting CodeGraph: Repository-Level Structural Retrieval.

### Slide 2: The Ambiguity of Natural Language in Agentic Coding
*   **Goal:** Tell a relatable story about the everyday developer experience with coding agents, highlighting why natural language queries often aren't specific enough for text retrieval alone.
*   **Visual:** TikZ diagram illustrating a common situation: a developer writes a natural language prompt (e.g., "fix the permissions logic") which is too abstract to map to the specific file (`global_settings.py`) using text similarity alone.
*   **Message:** More and more developers are using AI coding agents every day to navigate large repositories. But there's a common friction point: natural language queries are often abstract and not specific enough. When a developer asks an agent to fix a bug, their words rarely match the exact class or file names (a vocabulary mismatch). Because of this ambiguity, retrieving the right files using pure text similarity is incredibly difficult. We can solve this relatable problem by leveraging the code's inherent structure instead of just its text.

### Slide 3: Code is a Graph, Not Flat Text
*   **Goal:** Introduce the fundamental paradigm shift from text similarity to structural traversal.
*   **Visual:** TikZ diagram comparing flat text blocks versus a connected graph with `IMPORTS`, `CALLS`, and `INHERITS` edges.
*   **Message:** Code is not text; it's a deterministic network. We use a classic algorithm (Personalized PageRank) to propagate relevance structurally rather than relying on stochastic LLM queries inside the retrieval loop.

### Slide 4a: System Architecture - Indexing Phase (Overview)
*   **Goal:** Introduce how the codebase is converted from raw text to a structured graph.
*   **Visual:** The high-level Indexing Phase pipeline (Source Code -> Tree-sitter -> AST -> Neo4j).
*   **Message:** Before any agent asks a question, we have to build the world. This is the Indexing Phase, where we transform raw source code into a persistent property graph. It's done once and queried infinitely.

### Slide 4b: The 4-Entity Model & Graph Construction
*   **Goal:** Explain the chosen level of abstraction and why coarse-grained entities matter.
*   **Visual:** A simple graph example illustrating the 4-entity model (Files, Classes, Functions, Methods) connected by explicit structural edges (`CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS_FROM`).
*   **Message:** A crucial methodological choice is deliberately avoiding full AST ingestion. Denser representations dilute retrieval mass. Instead, we extract a coarse-grained, strict 4-entity model connected by pure syntactical dependencies. This precise, execution-aware structure is then loaded into a graph database (Neo4j/GDS) for fast algorithmic traversal.

### Slide 5a: System Architecture - Retrieval Phase (Overview)
*   **Goal:** Introduce the high-level deterministic retrieval pipeline.
*   **Visual:** The Retrieval Phase pipeline from the paper (Query -> Seed Selector -> PPR Ranker -> Ranked Context).
*   **Message:** This is the strongest point of the system: moving away from stochastic LLM generation to a fully deterministic graph operation. Let's look at exactly what happens when a query is submitted.

### Slide 5b: Walkthrough - The Anatomy of a Query
*   **Goal:** Provide one tight, concrete walkthrough showing the journey from prompt to final context payload (keep under 60-75 seconds).
*   **Visual:** A clean, minimal visual showing the core flow without over-animating intermediate artifacts: Query -> Seeds -> Propagation -> Ranked Context.
*   **Message:** To understand the mechanics, let's trace one query. We extract keywords and map them to graph seeds. From there, Personalized PageRank takes over, diffusing relevance across structural edges while penalizing generic hubs. The result is a mathematically rigorous ranking of context snippets, achieved deterministically.

### Slide 6: Evaluation Setup (SWE-bench Lite)
*   **Goal:** Legitimize the evaluation metric and clearly define what "success" means in this context.
*   **Visual:** Simple flow: GitHub Issue (Natural Language) -> Retriever -> Ranked Files (AI Context).
*   **Message:** We evaluated on 300 real-world GitHub issues. But what does success actually mean here? Our specific task is: given the natural language issue, accurately rank the specific files that the human developer ultimately modified in their patched solution. We do this under a fixed context budget, mirroring exactly how an agent operates.

### Slide 7: Quantitative Results
*   **Goal:** Prove empirical success.
*   **Visual:** Table II from the paper showing the progression from BM25 (58.0%) to Uniform PPR (74.0%).
*   **Message:** Graph propagation drives a massive 16-point gain over the strongest text baseline. 

### Slide 8: The Reachability Bottleneck
*   **Goal:** Share the deepest technical insight of the paper.
*   **Visual:** Figure 5 from the paper (Failure Taxonomy: 78 Zero-Recall Failures split into Connectivity Gaps and Semantic Gaps).
*   **Message:** The core insight is this: if the initial seeds miss the target neighborhood entirely, no ranking mechanism can recover them. "Seed reachability" is the true ceiling for agent retrieval. This distinguishes failures of graph connectivity from failures of semantic meaning.

### Slide 9a: The CodeGraph Ecosystem
*   **Goal:** Show the practical usability of the system and the specific interfaces built around it.
*   **Visual:** A nicely designed tri-node TikZ diagram connecting the core engine to three interfaces:
    1. **MCP Server:** Callouts highlighting the available tools (e.g., `get_relevant_context`, `query_dependencies`).
    2. **CLI:** Callouts highlighting important commands (e.g., `codegraph init`, `codegraph query`, `codegraph serve`).
    3. **Web Visualizer:** Mentioned as the structural debugging interface.
*   **Message:** This isn't just an abstract experiment; it's a fully realized toolset. Agents interact via standard MCP tools for context and dependencies, developers use the CLI for fast repository querying, and we built a web visualizer for structural debugging.

### Slide 9b: The Web Visualizer in Action
*   **Goal:** Provide a concrete look at the debugging capabilities without taking up too much time.
*   **Visual:** A high-quality screenshot of the Web Visualizer interface, showing a graph layout of a query result or seed propagation.
*   **Message:** To briefly touch on the visualizer: this interface is how we actually debug retrieval failures. Instead of guessing why an agent missed a file, we can visually inspect the seeds, see exactly where the graph connectivity breaks, and understand the flow of relevance. It turns the "black box" of retrieval into an observable graph.

### Slide 10: Conclusion & Future Work
*   **Goal:** End strongly by summarizing what was shown, why it matters, and the limiting factor, leaving the audience eager to read the paper.
*   **Visual:** A clean, punchy summary of the core takeaways (What we showed, Why it matters, The limiting factor), with a brief nod to future work.
*   **Message:** To wrap up: We showed that code structure beats pure text for context retrieval. This matters because it gives agents the deterministic reliability they desperately need. The limiting factor remains seed reachability. As for future work, we are actively extending to Java, TypeScript, and Spring Boot. If you want the full breakdown of how this graph pipeline is built, I highly encourage you to read the paper!

### Slide 11: Thank You & Q&A
*   **Goal:** End on a professional, academic note and open the floor for discussion.
*   **Visual:** A clean "Thank You" slide with your contact details/links, and "Questions?".
*   **Message:** Thank you so much for your time and attention. I'd be happy to take any questions.

## Visual Requirements
1. Use existing Beamer theme (Dark Navy).
2. Port architectural diagrams and evaluation tables directly from the paper using TikZ/Booktabs.
3. Keep slides uncluttered; rely on the speaker to deliver the nuance.
