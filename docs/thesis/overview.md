# Thesis alignment — system overview

CodeGraph is the implementation subject of the thesis in `thesis/`. This page links **research narrative** to **code/docs** for agents writing or reviewing thesis content.

---

## Research question (summary)

How effectively can **graph-based retrieval** (static dependency graph + Personalized PageRank) locate relevant source files for real-world software engineering tasks, compared to text-only baselines, using **natural-language issue descriptions** without embeddings?

---

## System role in the thesis

| Thesis concept | CodeGraph component |
|----------------|---------------------|
| Code property graph | Neo4j: File/Class/Function/Method + 4 edge types |
| Issue → file ranking | `run_core_retrieval` / SWE-bench harness |
| Explainability | `codegraph explain`, MCP `include_explanations` |
| Agent integration | MCP `get_relevant_context` |
| Evaluation | SWE-bench Lite, 300 instances, file-level Recall@k |

Chapters: `thesis/chapters/` — especially chapter 3 (design), 4 (implementation), 5 (evaluation).

---

## Claims agents may cite (verify in chapter 5)

- Benchmark: **SWE-bench Lite** (300 Python issues, 12 repos)
- Primary metric: **Recall@10** (target file in top 10 ranked files)
- Also: **MRR**, zero-recall count
- Best reported configuration: **~74% R@10** (see [evaluation.md](evaluation.md) — must match LaTeX, not outdated README)

Always prefer numbers from `thesis/chapters/chapter5_evaluation_results.tex` over informal docs.

---

## GUI figures

Thesis assets under `thesis/assets/` (e.g. ranked results, seed signals, graph UI). Generated from `codegraph visualize` workflows.

---

## Writing workflow

Thesis skill (Cursor): `.cursor/skills/thesis-writing/SKILL.md` (Gemini CLI redirects from `.gemini/skills/thesis-writing/`)  
Combine script: `thesis/scripts/combine_thesis.py`

When implementation changes, update thesis **and** [evaluation.md](evaluation.md) together.

## Evaluation reproduction

Harness: [../guides/evaluation-harness.md](../guides/evaluation-harness.md)  
Artifacts: `evaluation/results/*/summary.json`
