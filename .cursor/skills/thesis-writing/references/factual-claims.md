# Factual Claims (agents)

Prevents thesis prose from drifting from implementation or stale docs.

## Authority order

**System behavior, architecture, CLI/MCP, defaults:**

1. `docs/README.md` index → relevant `docs/concepts/`, `docs/reference/`, `docs/guides/`
2. `DECISIONS.md` (ACTIVE)
3. Source code only when docs are silent or user asks to verify drift

**Evaluation numbers:**

1. `thesis/chapters/chapter5_evaluation_results.tex` — PDF narrative
2. `evaluation/results/<run_id>/summary.json` — machine-readable run
3. `docs/thesis/evaluation.md` — agent bridge

Never use root `README.md` or `docs/CodeGraphContext-Docs-From-Github/` as authority.

## Benchmark (safe to state)

| Item | Value |
|------|-------|
| Dataset | SWE-bench **Lite**, 300 Python issues |
| Input | Issue text only (no embeddings for ranking) |
| Gold | Files in human merge patch |
| Primary metric | **Recall@10** (file-level) |
| Also | R@5, MRR, zero-recall @10 |

## Numbers (verify before every cite)

- Harness `iteration_3_full`: **73.33%** mean R@10, 80 zero-recall @10, MRR 0.443 — see `evaluation/results/iteration_3_full/summary.json`
- Thesis Ch.5 may state **~74.0%** for optimal config (rounding/wording). **Do not "fix" LaTeX to 73.33 without user approval.**
- Trajectory (+32pp vs early BM25): qualitative steps in Ch.5 — do not invent intermediate percentages

## Implementation ↔ thesis mapping

See `docs/thesis/overview.md` for: code graph, `run_core_retrieval`, MCP tools (exactly 2), `codegraph explain`.

## Related work positioning

- vs embeddings: `docs/thesis/related-work.md`
- vs CodeGraphContext: inspiration only under `docs/CodeGraphContext-Docs-From-Github/` — do not copy MCP surface (DEC-007)

## Discussion pitfalls

- **Zero-recall** often = graph reachability from seeds, not weak ranking alone
- Static Python, no dynamic dispatch — honest limitation in Ch.6

## When changing config or seeds

Re-run benchmark (`docs/guides/evaluation-harness.md`, at least `--limit 50`) before updating Ch.5 numbers.
