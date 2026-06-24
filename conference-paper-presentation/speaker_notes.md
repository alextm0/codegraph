# CodeGraph SCSS 2026 Presentation: 10-Minute Speaker Notes

## Overview
- **Total Time:** 10 minutes (approx. 8:45 - 9:15 speaking, leaving time for Q&A).
- **Pacing:** ~1 minute per slide.
- **Goal:** Drive the narrative from "why this matters" to "how it works" to "what it achieved" and end with a "scientific takeaway".

---

## Slide 1: Title (0:00 - 0:45)
**"CodeGraph: Repository-Level Structural Retrieval"**
- **Script:** "Hello everyone. My name is Toma Alexandru-Mihai, and today I am presenting CodeGraph. This project focuses on deterministic repository retrieval for coding agents under fixed context budgets. As coding agents become more autonomous, ensuring they receive the correct codebase context is the most critical hurdle to solving real-world software issues."

## Slide 2: Problem Context (0:45 - 1:45)
**"Coding agents fail when issue text and identifiers do not line up"**
- **Script:** "Autonomous coding agents need the exact, relevant code files placed into their limited context window to produce valid patches. But there is a fundamental vocabulary gap: issue descriptions are written in natural language, while the code relies on specific, rigid identifiers. When these don't line up, the agent hallucinates or fails completely."

## Slide 3: Why existing retrieval is insufficient (1:45 - 2:45)
**"Sparse and dense retrieval miss structural reachability"**
- **Script:** "Traditionally, we use sparse lexical search like BM25 or dense embeddings like CodeBERT. BM25 requires exact lexical overlap, missing dependencies that share no vocabulary. Dense retrieval captures semantic similarity but ignores the explicit execution edges of the code. A repository isn't a flat bag of tokens; it's a structural graph. CodeGraph solves this by navigating structural reachability—ranking through actual imports, calls, and inheritance."

## Slide 4: CodeGraph's Core Idea (2:45 - 3:45)
**"The query chooses where relevance starts; the graph decides the flow"**
- **Script:** "This brings us to our core idea. We explicitly separate lexical entry from structural ranking. First, we use natural language issue text strictly to place initial probability mass on the graph—this is lexical seeding. Once we have these entry points, the final relevance ranking is computed entirely by graph topology. The graph structure itself decides where relevance flows, without relying on non-deterministic LLM judgements."

## Slide 5: The Pipeline (3:45 - 4:45)
**"The pipeline bridges raw source code to a ranked context window"**
- **Script:** "Here is the full architecture. Our pipeline has two main phases. We parse the source code and build the dependency graph during the indexing phase. Then, per query in the retrieval phase, we select seeds using the issue text, run Personalized PageRank over the graph, and finally package the highest-ranked nodes into a context window."

## Slide 6: Indexing Phase (4:45 - 5:45)
**"Behind the scenes: The Indexing Phase"**
- **Script:** "During the offline indexing phase, we use Tree-sitter to build a four-entity model—files, classes, functions, and methods—connected by explicit edges like CONTAINS, IMPORTS, CALLS, and INHERITS_FROM. Our two-pass build is conservative. If a call is ambiguous, we drop it in favor of precision over false connectivity."

## Slide 7: Retrieval Phase (5:45 - 6:45)
**"Behind the scenes: The Retrieval Phase"**
- **Script:** "During the retrieval phase, we combine multi-signal seed selection with exact matrix multiplication. This is crucial: the exact same seeds will always produce the exact same ranking. Finally, we deduplicate these ranked nodes and deliver them within a strict 6,000-token budget."

## Slide 8: Results (6:45 - 7:45)
**"Global structural ranking drives the empirical gain"**
- **Script:** "Does it work? Yes. As you can see in the trajectory chart, CodeGraph achieves a Recall@10 of 74.0%. This is a massive leap, improving upon the strongest lexical BM25 baseline by 16.0 percentage points. We also tested a naive one-hop graph expansion, which only reached 51.0%. This proves that our performance gains don't come from blindly adding neighboring nodes, but from the global structural ranking that Personalized PageRank provides."

## Slide 9: Reachability Ceiling (7:45 - 8:45)
**"The ultimate retrieval ceiling is seed reachability"**
- **Script:** "I want to highlight our most memorable scientific takeaway. CodeGraph proves that deterministic lexical-to-graph retrieval works efficiently, but the ultimate retrieval ceiling is seed reachability. When we analyzed our 78 zero-recall failures, we found they split cleanly into connectivity gaps and semantic gaps. If the seeds land in the right structural neighborhood, the ranking works. When they don't, no ranking tweak can recover the target."

## Slide 10: Conclusion (8:45 - 9:30)
**"Conclusion and Limitations"**
- **Script:** "In conclusion, deterministic structural retrieval is an effective and fast solution, maintaining sub-second median latency. We acknowledge boundaries like static-analysis dependence, Python-only scope, and file-level evaluation, but this reachability frontier is exactly what the field must tackle next."

## Slide 11: Q&A (9:30 - 10:00)
**"Thank you! Questions?"**
- **Script:** "Thank you very much for your time and attention! I would be happy to take any questions."
