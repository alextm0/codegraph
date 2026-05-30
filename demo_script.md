# CodeGraph Thesis Defense Demo Script

This script provides a structured path for demonstrating the CodeGraph retrieval system during the thesis defense.

## Preparation
1. Ensure Neo4j is running and populated with the target repository (e.g., `flask`).
2. Start the visualizer:
   ```bash
   codegraph visualize --watch
   ```
3. Open the browser at `http://localhost:8000`.

## Scenario 1: The Lexical-Structural Synergy
**Goal:** Show how CodeGraph recovers relevant files that BM25 misses due to lexical mismatch.

1.  **Input Query:** "Fix the error where the session cookie is not being set correctly when using secure=True".
2.  **Observation - SEED.SIGNALS:**
    *   Point out that "session" and "cookie" are identified as seeds.
    *   Note that "secure" might match many utility functions, showing the need for IDF reweighting.
3.  **Observation - Ranked Results:**
    *   Show that `flask/sessions.py` is at the top.
    *   Compare with a "BM25 only" mental model (where `flask/app.py` might be higher due to keyword density).
4.  **Observation - Topological Map:**
    *   Focus on `sessions.py`. Show the incoming `CALLS` edges from `app.py`.
    *   Explain how probability mass flows from the `session` seed nodes to the actual implementation.

## Scenario 2: System Observability & Determinism
**Goal:** Demonstrate the transparency of the ranking process.

1.  **Node Inspection:**
    *   Click on a high-ranked node (e.g., `SecureCookieSessionInterface`).
    *   Show the `NODE.INSPECT` panel with its qualified name, file path, and PPR score.
    *   Show the source code snippet extracted by the interface.
2.  **Structural Path:**
    *   Trace the path from a seed node to the target file.
    *   Explain "Topological Determinism": the agent is restricted to this verified graph.

## Scenario 3: Agent Integration (Optional/Narrative)
**Goal:** Show how the Model Context Protocol (MCP) bridge works.

1.  **Explain the Interface:**
    *   Describe how an agent (like Claude or Gemini) calls `get_relevant_context`.
    *   Explain the token-aware packaging: the agent gets exactly what it needs within its context budget.

## Summary Points to Emphasize
*   **Speed:** Sub-250ms query latency.
*   **Precision:** Ranking is based on actual code dependencies (Tree-sitter parsed).
*   **Transparency:** Every result has a mathematical and structural justification.
