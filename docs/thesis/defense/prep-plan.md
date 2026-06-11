# Thesis Defense Preparation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish deep technical authority and presentation readiness for the CodeGraph thesis defense (July 1-3).

**Architecture:** Iterative "Socratic Loop" across six technical domains: Discovery (reading code) &rarr; Breakdown (logic walkthrough) &rarr; Stress Test (Mock Q&A) &rarr; Gap Analysis (AI correction).

**Tech Stack:** Python (3.12), Neo4j (5.x), GDS, tree-sitter, FastAPI, React, D3.js.

---

### Task 1: The Ingestion Pillar (Phase 1)

**Files:**
- Research: `src/codegraph/core/parser/`
- Research: `src/codegraph/core/graph/graph_builder.py`
- Research: `src/codegraph/core/graph/resolution.py`

- [ ] **Step 1: Discover Tree-Sitter & Entity Extraction**
    - Walkthrough `python_parser.py` and `extractors.py`.
    - Understand how we go from raw bytes to `FileEntities`.
- [ ] **Step 2: Breakdown Static Resolution**
    - Examine `resolution.py`. 
    - Trace the logic of `_resolve_callee`: Import Map &rarr; Same-File &rarr; Global Unique.
- [ ] **Step 3: Graph Construction Mechanics**
    - Study `graph_builder.py`.
    - Understand the two-pass build: (1) Nodes/Containment, (2) Cross-file links.
- [ ] **Step 4: Stress Test (Mock Q&A)**
    - Answer 3 Mock Questions:
        1. "How does the system handle namespaced calls like `self.db.query()`?"
        2. "What happens if a file has a syntax error during `rebuild`?"
        3. "Why are ambiguous calls explicitly dropped from the graph?"
- [ ] **Step 5: Authority Gap Analysis**
    - Review answers vs. implementation code. Refine the "Technical Authority" version of each answer.

---

### Task 2: The Retrieval Pillar (Phase 2)

**Files:**
- Research: `src/codegraph/core/graph/ppr.py`
- Research: `src/codegraph/core/retrieval/seed_selection.py`
- Research: `src/codegraph/core/retrieval/post_processing.py`

- [ ] **Step 1: Personalized PageRank (PPR) Deep Dive**
    - Walkthrough `ppr.py`.
    - Understand `damping_factor`, `max_iterations`, and `retrieval_mode`.
- [ ] **Step 2: Seed Selection Logic**
    - Examine `seed_selection.py`.
    - Trace how we extract entities from a task string and combine them with BM25.
- [ ] **Step 3: IDF & Post-Processing**
    - Study `apply_idf_weights()` in `post_processing.py`.
    - Understand why we down-weight "hub" nodes.
- [ ] **Step 4: Stress Test (Mock Q&A)**
    - Answer 3 Mock Questions:
        1. "Explain the mathematical difference between Uniform and Weighted restart in PPR."
        2. "Why do we recreate the GDS projection on every query?"
        3. "How do 'Issue Hints' (weights) help in a bug-fixing context?"
- [ ] **Step 5: Authority Gap Analysis**
    - Compare theoretical understanding of PageRank to your actual implementation.

---

### Task 3: The Architecture Pillar (Phase 3)

**Files:**
- Research: `src/codegraph/visualizer/`
- Research: `src/codegraph/mcp/`
- Research: `frontend/src/components/graph/`

- [ ] **Step 1: Real-Time Sync (WebSockets)**
    - Walkthrough `routes.py` and `app.py` in the visualizer.
    - Understand the status broadcast during rebuilds.
- [ ] **Step 2: Frontend State & Graph Physics**
    - Examine `GraphCanvas.tsx` and `graphHelpers.ts`.
    - Understand how D3.js force simulation manages thousands of nodes.
- [ ] **Step 3: MCP & Tool Design**
    - Study `mcp/tools.py`.
    - Understand the logic behind `get_relevant_context` and why it's a single entry point for agents.
- [ ] **Step 4: Stress Test (Mock Q&A)**
    - Answer 3 Mock Questions:
        1. "How does the UI render code snippets from the disk securely?"
        2. "What was the biggest challenge in scaling the force-graph for large repos?"
        3. "Why use WebSockets instead of a simple REST polling mechanism for rebuilds?"
- [ ] **Step 5: Authority Gap Analysis**
    - Bridge the gap between "the UI works" and "I understand the data flow from server to browser."

---

### Task 4: The Scientific Pillar (Phase 4)

**Files:**
- Research: `evaluation/`
- Research: `docs/thesis/evaluation.md`
- Research: `evaluation/results/iteration_2_top_30/summary.json`

- [ ] **Step 1: Evaluation Harness Mechanics**
    - Walkthrough `swe_bench_runner.py`.
    - Understand how we automate the testing of 300 GitHub issues.
- [ ] **Step 2: Metric Definition & Claims**
    - Study `metrics.py`.
    - Be able to define **Recall@10** and **MRR** from memory.
- [ ] **Step 3: Ablation Study Analysis**
    - Review `ablations.py` and the results.
    - Understand which graph edges (CALLS vs IMPORTS) are the most critical for performance.
- [ ] **Step 4: Stress Test (Mock Q&A)**
    - Answer 3 Mock Questions:
        1. "Explain the 'Reachability Ceiling'—why can't the system reach 100% recall?"
        2. "Why is CodeGraph's 24% gain over BM25 significant?"
        3. "How does the evaluation repo-manager ensure a clean state for every instance?"
- [ ] **Step 5: Authority Gap Analysis**
    - Ensure your explanation of "why it works" matches your empirical data.

---

### Task 5: Demo & Rehearsal (Phase 5)

**Files:**
- Research: `demo_script.md`
- Research: `docs/guides/demo-defense.md`

- [ ] **Step 1: Live Demo Dry Run (Visualizer)**
    - Perform Act 1 of the script. Focus on highlighting "Reasoning Paths."
- [ ] **Step 2: Live Demo Dry Run (MCP & CLI)**
    - Perform Act 2 and 3. Practice explaining the tool calls as they happen.
- [ ] **Step 3: Fallback & Trouble Shooting Drill**
    - Practice recovering from a "Neo4j Down" or "Empty Graph" scenario live.
- [ ] **Step 4: Final Stress Test (Generalist Examiner)**
    - A random selection of 5 questions from all previous phases.
- [ ] **Step 5: Commitment & Finalization**
    - Commit any final doc updates or demo fixes to the repo.
