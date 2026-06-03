# Evaluation (SWE-bench Lite)

**Authoritative prose:** `thesis/chapters/chapter5_evaluation_results.tex`  
**Authoritative numbers (machine):** `evaluation/results/*/summary.json`  
This page bridges both for agents.

---

## Benchmark

| Property | Value |
|----------|-------|
| Dataset | SWE-bench **Lite** — 300 issues |
| Language | Python repos (Django, SymPy, matplotlib, sklearn, pytest, sphinx, …) |
| Input | GitHub issue text only |
| Gold | File(s) modified in human merge patch |
| Level | **File-level** Recall@k (not entity-level) |

---

## Metrics

| Metric | Definition |
|--------|------------|
| **Recall@k** | Fraction of instances where any gold file appears in top-k predicted files |
| **R@10** | Primary headline (agents inspect ~5–20 files) |
| **R@5** | Stricter cut |
| **MRR** | Mean of 1/rank of first hit |
| **Zero-recall** | Count with no gold file in top-10 |

---

## Reported performance (verify before citing)

### Harness artifact: `iteration_3_full` (baseline, n=300)

From `evaluation/results/iteration_3_full/summary.json`:

| Metric | Value |
|--------|-------|
| mean Recall@10 | **73.33%** (0.7333) |
| mean Recall@5 | 63.0% |
| mean MRR | 0.443 |
| median MRR | 0.333 |
| zero-recall @10 | 80 instances |

### Thesis narrative (chapter 5)

The thesis states **~74.0% Recall@10** for the optimal configuration — may reflect rounding, slightly different run id, or final wording pass. **For the thesis PDF, use LaTeX.** For engineering, use `summary.json` from the run you actually executed.

### Improvement trajectory (qualitative)

Documented in thesis § eval trajectory:

1. Early baseline ~60% R@10 (BM25 / weak graph)
2. Uniform restart + damping 0.70 → ~72% band
3. IDF + seed refinements → low-74% band

Do not invent intermediate numbers — read chapter 5 tables.

---

## How to reproduce

Full instructions: [../guides/evaluation-harness.md](../guides/evaluation-harness.md)

```bash
pip install -e ".[bench]"
python -m evaluation.swe_bench_runner \
  --cache-dir .codegraph_cache \
  --output evaluation/results/my_run \
  --ablation baseline
```

Pilot: add `--limit 5`.

---

## Ablations (what was tested)

See `evaluation/ablations.py`:

- Drop one edge type (`no_calls`, `no_imports`, `no_inherits`)
- Directed vs undirected projection
- `no_idf`
- `ppr_weighted` vs uniform
- Damping sweeps (`alpha_*`, `uniform_alpha_070`)
- top-k sweeps

Production config = **baseline** + `config.yaml` PPR defaults (DEC-001).

---

## Known failure mode: reachability

**Zero-recall** instances (~80/300 at iter-3) often mean the gold file is **not reachable** from any seed in the static graph within 10 hops — not merely low rank. Thesis discusses this as the main structural ceiling.

Agents writing discussion sections should read chapter 6 limitations too.

---

## Agent citation rules

1. Never cite README marketing numbers without checking this file + LaTeX
2. New benchmark claim → attach `summary.json` path in PR
3. Config change to seeds/PPR → re-run at least `--limit 50` before thesis updates
