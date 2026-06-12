# SWE-bench evaluation harness

Reproducible benchmark for **file-level retrieval** on SWE-bench Lite. Used for thesis Chapter 5 and tuning defaults.

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
# Use the project venv; unbuffered stderr shows live progress
.venv/bin/python -m evaluation.swe_bench_runner \
  --cache-dir .codegraph_cache/repos \
  --output evaluation/results/my_run \
  [--limit 5] \
  [--ablation baseline] \
  [--grouping repo_commit] \
  [--verbose]
```

**While a run is in progress:**

- **stderr** — `[bench …]` lines for each phase (clone, parse, build, query) and per-instance HIT/MISS
- **`evaluation/results/<run>/progress.json`** — running Recall@10, error count, last instance
- **`per_instance.jsonl`** — appended after each instance (safe to tail)

First clone of a large repo (Django, SymPy) can take **several minutes**; git `--progress` output is shown on stderr.

| Flag | Purpose |
|------|---------|
| `--limit N` | Pilot on first N instances (django-heavy slice — not representative of full Lite) |
| `--ablation NAME` | Config from `evaluation/ablations.py` (`ABLATIONS` list) |
| `--grouping repo_commit` | Reuse graph per repo+commit (default, ~297 groups) |
| `--no-grouping` | Rebuild per instance (slow) |
| `--instance-ids-file PATH` | JSON list of `instance_id` strings, or `file.json:tier_key` for tier objects |
| `--repo-prefix PREFIX` | Filter dataset to repos matching prefix |
| `--subset-name NAME` | Label for `summary.json` metadata |

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

**Production defaults** match `AblationConfig(name="baseline")` + uniform α=0.70, top_k=30 in `config.yaml`.

---

## Stored results

`evaluation/results/<run_name>/`:

- `per_instance.jsonl` — one JSON line per issue
- `summary.json` — aggregated means/medians

See [`evaluation/results/README.md`](../../evaluation/results/README.md) for canonical artifacts.

| Run | mean Recall@10 | zero-recall @10 | Notes |
|-----|----------------|-----------------|-------|
| **iteration_2_top_30** | **74.0%** | **78** | Thesis headline (`uniform_top_k_30`) |
| iteration_3_full | 73.3% | 80 | Harness parity reference (`baseline`) |

Re-running today may not exactly reproduce iter2 numbers; cite the artifact you executed or LaTeX chapter 5.

---

## Ablation sweep (sequential)

Verify harness wiring, then run a preset of ablations one after another:

```bash
# 1. Pre-flight (add --live for Neo4j)
.venv/bin/python -m evaluation.verify_benchmark_setup --live

# 2. Quick pilot (10 instances)
.venv/bin/python -m evaluation.run_ablation_sweep --preset quick --limit 10

# 3. Full baseline run (300 instances)
.venv/bin/python -m evaluation.swe_bench_runner \
  --output evaluation/results/my_full_run \
  --ablation baseline \
  --grouping repo_commit

# Resume interrupted sweep
.venv/bin/python -m evaluation.run_ablation_sweep --preset quick --limit 10 --skip-completed
```

Outputs under `--output-root` (default `evaluation/results/ablation_sweep`):

- `<ablation>/summary.json`, `per_instance.jsonl`, `progress.json`, `run.log`
- `sweep_summary.json` — comparison table + **best** config by Recall@10

Presets: `quick`, `full` (see `evaluation/ablations.py` → `PRESETS`).

---

## Supporting scripts

| Script | Role |
|--------|------|
| `verify_benchmark_setup.py` | Pre-flight harness + config checks |
| `run_ablation_sweep.py` | Run ablation preset sequentially |
| `compare_runs.py` | Diff two `summary.json` files |
| `report.py` | Generate reports from results |
| `error_analysis.py` | Dig into zero-recall cases |
| `local_correctness_test.py` | Smaller sanity runs |
| `repo_manager.py` | Clone cache, `checkout_commit` |
| `dataset.py` | Load SWE-bench Lite, instance grouping |
| `instance_filter.py` | Load instance ID lists from JSON |

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
- Headline metrics → **iteration_2_top_30** unless a new full run beats it on both R@10 and zero-recall
- Changing PPR/seed defaults requires re-running at least a `--limit 50` pilot
- Evaluation excludes `tests/` at parse time — different from dev `config.yaml` excludes

---

## Relation to production MCP

The harness calls **`run_core_retrieval`** with the same `config.yaml` `seed_selection` settings as MCP/CLI (`exclude_seed_paths`, signal weights, issue hints).

Differences from interactive use:

- No MCP auto-index
- Clears DB between repo groups; reuses BM25 index + GDS projection per `(repo, commit)` group
- File-level aggregation for metrics via `file_paths_from_ppr_results` (not entity-level token budget)

Optional: `--file-rank-by max_score` for file ordering experiments (default `first_entity`).

`summary.json` records `git_commit` when the runner is executed inside a git checkout.
.
