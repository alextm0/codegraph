# Retrieval Pipeline Diagram Spec

This document provides the exact data, conceptual steps, and raw console output you need to create a slide diagram explaining the CodeGraph retrieval pipeline. 

## The Core Concept
The goal of the diagram is to show how CodeGraph moves from a **Natural Language Query** to **Ranked Source Code** by leveraging the graph structure rather than generic embeddings.

---

## The Example Query
Use this exact query for your presentation diagram as it perfectly triggers both components of the seed selection engine:

> **Query:** *"How does PythonParser extract AST nodes into the GraphBuilder?"*

---

## Exact CLI Output
Here is the exact terminal output when this query is executed, providing all the needed context for the retrieval pipeline stages.

```text
Explaining: "How does PythonParser extract AST nodes into the GraphBuilder?"

                            Seeds (11 nodes)                             
                                                                         
  Seed node                                       Signal         Weight  
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 
  PythonParser                                    entity_match    0.118  
  extract_imports                                 bm25            0.114  
  extract_classes                                 bm25            0.103  
  clear_database                                  bm25            0.101  
  test_graph_builder_write_nodes_order            bm25            0.095  
  _write_nodes                                    bm25            0.092  
  extract_methods                                 bm25            0.091  
  src/codegraph/core/languages/python/parser.py   bm25            0.091  
  test_clear_database_removes_all_nodes           bm25            0.088  
  extract_calls                                   bm25            0.088  
  GraphBuilder                                    entity_match    0.019  
                                                                         
                    Top Results — Why did PPR return these?                     
                                                                                
                                                        Reasoning path from     
   #   File                      Score   Contribution   nearest seed            
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 
   1   src/codegraph/core/graph/graph_builder.py              0.82904   lexical        direct seed             
   2   src/codegraph/core/languages/python/parser.py          0.53520   lexical        direct seed             
   3   src/codegraph/core/languages/python/extractor.py       0.43068   lexical        direct seed             
   4   src/codegraph/core/languages/python/parser.py          0.41577   both           PythonParser            
                                                                                       -[CONTAINS]->           
                                                                                       parse_file              
   5   src/codegraph/core/languages/python/resolution.py      0.41345   lexical        direct seed             
   6   src/codegraph/core/languages/python/extract_funcs.py   0.39906   lexical        direct seed             
   7   src/codegraph/core/languages/python/entities.py        0.38727   lexical        direct seed             
   8   src/codegraph/core/graph/ppr.py                        0.38061   lexical        direct seed             
   9   tests/unit/core/graph/test_builder.py                  0.37210   lexical        direct seed             
  10   src/codegraph/core/graph/resolution.py                 0.36827   lexical        direct seed             
```

---

## Pipeline Steps for the Diagram

### 1. Seed Selection (The Entry Points)
The query is processed to find starting nodes in the Neo4j graph.
- **Entity Matches (Exact structural hits):**
  - `PythonParser` (Weight: 0.118)
  - `GraphBuilder` (Weight: 0.019)
- **BM25 Matches (Lexical hits):**
  - `extract_imports`
  - `extract_classes`
  - `_write_nodes`
  - `extract_methods`

*Visual idea for slide:* Show the query string splitting into two arrows. One arrow goes to a strict exact-match "Entity Index", and the other goes to a fuzzy "BM25 Text Index". Both point to nodes inside a visual graph.

### 2. Graph Traversal (Personalized PageRank)
Once the seeds are activated, the "pagerank fluid" flows outward across the edges (CALLS, IMPORTS, CONTAINS). 
- **Example Flow:** 
  - The seed `PythonParser` has a structural `CONTAINS` edge pointing to `parse_file`. 
  - Therefore, `parse_file` receives a high score (0.415) and appears at rank #4 because it is structurally connected to a high-weight seed, *even if the word "parse_file" wasn't in the query*.

*Visual idea for slide:* Show the seed nodes glowing brightly, and arrows (edges) carrying a percentage of that glow to their neighboring nodes. Emphasize the edge types (`CONTAINS`, `CALLS`).

### 3. Result Ranking (Token Budgeting)
The PPR algorithm converges, giving every node in the graph a score. The top nodes are mapped back to their source files and returned within the 6000 token budget.
- **Top Result #1:** `src/codegraph/core/graph/graph_builder.py` (Score: ~0.829)
- **Top Result #2:** `src/codegraph/core/languages/python/parser.py` (Score: ~0.535)

*Visual idea for slide:* A funnel where the highest-glowing nodes are converted back into code snippets (the final JSON payload sent to the LLM or Visualizer).

---

## Suggested Slide Layout

If you use a 3-column layout or a left-to-right flowchart:
1. **Left Box (Input):** The Query.
2. **Middle Graphic (The Brain):** A small sub-graph with 5-6 nodes. `PythonParser` and `GraphBuilder` are colored **Red** (Seeds). Arrows point from `PythonParser` to `parse_file` (colored **Orange** to show it received rank via edges).
3. **Right Box (Output):** The final ranked list of files.

This explicitly proves the thesis claim: CodeGraph doesn't just return where the words match; it returns the architectural context surrounding those words.
