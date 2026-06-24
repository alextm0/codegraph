# CodeGraph SCSS 2026 Presentation: 10-Minute Speaker Notes

## Overview
- **Total Time:** 10 minutes (approx. 8:45 - 9:15 speaking, leaving time for Q&A).
- **Pacing:** ~1 minute per slide.

---

## Slide 1: Title (0:00 - 0:45)
- **Script:** "Hello everyone. My name is Toma Alexandru-Mihai, and today I am presenting CodeGraph. This project focuses on deterministic repository retrieval for coding agents under fixed context budgets."

## Slide 2: Why repository retrieval matters for coding agents (0:45 - 1:45)
- **Script:** "Before talking about CodeGraph itself, the key problem is simple. A coding agent starts from an issue description, but it cannot fix the repository unless it first receives the right context. So the first challenge is not generation alone, it is retrieval—selecting the relevant part of a much larger repository. An agent can only solve a task if the right repository context is retrieved first."

## Slide 3: Text alone is not enough for repository retrieval (1:45 - 2:45)
- **Script:** "The challenge is that the issue is described in natural language, but the repository is not organized as plain text. It is organized through files, classes, functions, and dependencies like imports and calls. So if retrieval relies only on text similarity, it misses the structural relationships that actually connect relevant code. CodeGraph bridges this gap between language and structure."

## Slide 4: Core idea (2:45 - 3:45)
- **Script:** "This brings us to our core idea. We explicitly separate lexical entry from structural ranking. The issue text does not directly rank the repository; it only places initial probability mass on plausible entry points. Then Personalized PageRank propagates relevance through the dependency graph, so the final ranking comes from repository structure, not only from text overlap. The query chooses where relevance starts, the graph determines where relevance flows."

## Slide 5: Indexing Phase (3:45 - 4:45)
- **Script:** "CodeGraph has two phases. First is the Indexing Phase. During this phase, we build the graph once before any query arrives. We use Tree-sitter to parse source files into a syntax structure, modeling files, classes, functions, and methods as graph entities. We add explicit structural links such as CONTAINS, IMPORTS, CALLS, and INHERITS_FROM. The result is a persistent repository graph used later during retrieval."

## Slide 6: Retrieval Phase (4:45 - 5:45)
- **Script:** "Once the graph exists, retrieval becomes a deterministic per-query process. The Retrieval Phase uses three complementary signals for seed selection: entity match, BM25 keyword search, and issue path hint. Then, Personalized PageRank computes a global ranking over reachable code entities. The output is deduplicated and packaged as ranked context for the agent under a fixed 6,000-token budget. Because it uses exact matrix multiplication, the same seeds yield the same deterministic ranking."

## Slide 7: Evaluation on SWE-bench Lite (5:45 - 6:45)
- **Script:** "To see if this works, we evaluated on SWE-bench Lite, consisting of 300 real GitHub issues from 12 open-source Python repositories. The benchmark asks the system to start from a natural-language issue description and rank files so that the files modified in the human patch appear at the top of the list. Our primary metric is Recall@10, which matches the typical context budget of coding agents."

## Slide 8: Results (6:45 - 7:45)
- **Script:** "The results show that global structural ranking drives the empirical gain. CodeGraph reaches 74.0% Recall@10 at our main operating point. This improves over the strongest lexical baseline by 16.0 percentage points. We also tested a naive one-hop ego-graph expansion, which only reached 51.0%. This shows that global ranking, not local expansion, is what produces the real gain."

## Slide 9: Bottleneck and failure analysis (7:45 - 8:45)
- **Script:** "While CodeGraph improves performance, we also analyzed where it fails. The real retrieval ceiling is seed reachability. Of the 78 zero-recall cases, 40 were connectivity gaps and 38 were semantic gaps. This means retrieval quality is bounded by whether lexical signals place probability mass in the correct structural neighborhood. If lexical signals miss the correct neighborhood, ranking alone cannot recover the target."

## Slide 10: Conclusion (8:45 - 9:30)
- **Script:** "To conclude, this project shows three things. First, structure-aware retrieval works better than text-only retrieval for coding agents. Second, a deterministic lexical-to-graph pipeline can deliver strong retrieval quality with low latency. And third, the main open problem is seed reachability. We recognize current boundaries like static-analysis dependence and Python-only scope, but this reachability frontier is what the field must tackle next."

## Slide 11: Final questions slide (9:30 - 10:00)
- **Script:** "Thank you very much for your attention. I am happy to take any questions."
