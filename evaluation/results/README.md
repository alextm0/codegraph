# Benchmark result artifacts

## Canonical (thesis headline)

| Run | Path | R@10 | Zero-recall @10 |
|-----|------|------|-----------------|
| **iteration_2_top_30** | [`iteration_2_top_30/summary.json`](iteration_2_top_30/summary.json) | **74.0%** | **78** |

Use this artifact and `thesis/chapters/chapter5_evaluation_results.tex` for reported performance. Config: uniform PPR, α=0.70, top_k=30 (`uniform_top_k_30` ablation).

## Engineering reference (non-thesis)

| Run | Path | R@10 | Zero-recall @10 |
|-----|------|------|-----------------|
| iteration_3_full | [`iteration_3_full/summary.json`](iteration_3_full/summary.json) | 73.3% | 80 |

Harness uses `run_core_retrieval` (MCP/CLI parity). Numbers may differ slightly from iter2 if re-run today.

## Removed experiments

Iteration 4/5 sweeps (α=0.50, seed caps, tier subsets) did not beat iter2 on full SWE-bench Lite and were deleted from this tree.

## Agent rules

- Do not cite benchmark numbers without a `summary.json` in this directory.
- New claims require a new run folder and an update to [`docs/thesis/evaluation.md`](../docs/thesis/evaluation.md).
