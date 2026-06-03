# SWE-bench evaluation harness

Reproducible benchmark for **file-level retrieval** on SWE-bench Lite. Used for thesis Chapter 5 and tuning DEC-001 defaults.

**Code:** `evaluation/` package at repo root (installed via `pyproject.toml` `include`).

---

## What it measures

For each of **300** instances:

1. Clone repo at `base_commit` (grouped by `(repo, base_commit)` to reuse one graph per group)
2. Parse + `build_graph`
3. Run retrieval with **issue text only** as `task_description`
4. Rank files; compare to **gold files** from merged patch (`gold_patch_parser.py`)

Metrics (`metrics.py`):

- **Recall@5**, **Recall@10**
- **MRR** (first gold file rank)
- **instances_with_zero_recall** (gold not in top 10)

---

## Running the benchmark

**Prerequisites:**

```bash
pip install -e ".[bench]"
# Neo4j + GDS running with credentials in env or tests/config.yaml pattern
```

**Main runner:**

```bash
python -m evaluation.swe_bench_runner \
  --cache-dir .codegraph_cache \
  --output evaluation/results/my_run \
  [--limit 5] \
  [--ablation baseline] \
  [--grouping repo_commit]
```

| Flag | Purpose |
|------|---------|
| `--limit N` | Pilot on first N instances |
| `--ablation NAME` | Config from `evaluation/ablations.py` (`ABLATIONS` list) |
| `--grouping repo_commit` | Reuse graph per repo+commit (default, ~297 groups) |
| `--no-grouping` | Rebuild per instance (slow) |

**Retriever modes:** `ppr` (default), BM25-only baselines via `baselines.py` / runner flags.

---

## Ablation configurations

`evaluation/ablations.py` defines `AblationConfig`:

| Knob | Examples |
|------|----------|
| `relationship_types` | `no_calls`, `no_imports`, `no_inherits` |
| `orientation` | `directed_natural`, `directed_reverse` |
| `apply_idf` | `no_idf` |
| `ppr_config` | `ppr_weighted`, `uniform_alpha_070`, `top_k_10`, damping sweeps |

**Production defaults** match `AblationConfig(name="baseline")` + uniform α=0.70 in `config.yaml`.

---

## Stored results

`evaluation/results/<run_name>/`:

- `per_instance.jsonl` — one JSON line per issue
- `summary.json` — aggregated means/medians

Example **iteration_3_full** (`baseline`, 300 instances):

| Metric | Value |
|--------|-------|
| mean Recall@10 | **0.733** (~73.3%) |
| mean Recall@5 | 0.63 |
| mean MRR | 0.443 |
| zero-recall @10 | 80 instances |

Thesis text may round or report **74.0%** after later tuning — **always sync** [../thesis/evaluation.md](../thesis/evaluation.md) with `thesis/chapters/chapter5_evaluation_results.tex`.

---

## Supporting scripts

| Script | Role |
|--------|------|
| `compare_runs.py` | Diff two `summary.json` files |
| `report.py` | Generate reports from results |
| `error_analysis.py` | Dig into zero-recall cases |
| `find_killer_example.py` | Find illustrative failure/success |
| `local_correctness_test.py` | Smaller sanity runs |
| `repo_manager.py` | Clone cache, `checkout_commit` |
| `dataset.py` | Load SWE-bench Lite, instance grouping |

---

## Dashboard

```bash
pip install -e ".[dashboard]"
codegraph-bench-dashboard
```

Textual TUI over `evaluation/dashboard/` — monitor long runs.

---

## Agent rules

- Do not claim new benchmark numbers without a `summary.json` artifact
- Changing PPR/seed defaults requires re-running at least a `--limit 50` pilot
- Evaluation excludes `tests/` at parse time — different from dev `config.yaml` excludes

---

## Relation to production MCP

Same `run_core_retrieval` / `extract_seeds` / `ensure_graph_ready` as MCP, but:

- No MCP auto-index
- Clears DB between repo groups
- File-level aggregation for metrics (not entity-level token budget)
