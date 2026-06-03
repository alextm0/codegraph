# Cookbook — task recipes

Copy-paste workflows for demos, thesis, and agent testing. Assumes `codegraph init`, Neo4j running, and `codegraph rebuild` completed.

---

## Recipe 1: First context for a bugfix

```bash
codegraph query "fix authentication token expiry" \
  -e AuthService -e validate_token --compact
```

If results look wrong:

```bash
codegraph explain "fix authentication token expiry"
```

---

## Recipe 2: Refactor — find all callers

```bash
codegraph analyze deps validate_token --direction upstream --depth 2
```

Optional graph view:

```bash
codegraph analyze deps validate_token --direction upstream --viz
```

---

## Recipe 3: Agent prompt (Claude / Cursor)

```
Use CodeGraph MCP get_relevant_context for:
"add refresh token rotation to the login flow"
mentioned_entities: ["AuthService", "login"]
Then summarize which files to edit and why.
```

Follow with `query_dependencies` only if renaming public APIs.

---

## Recipe 4: Visualizer demo (Flask)

```bash
codegraph visualize
```

1. UI: init with `https://github.com/pallets/flask` OR use CLI `codegraph init` first
2. Wait for rebuild WebSocket events
3. Query: *"How does routing work?"*
4. Open top-ranked node → file panel

See [demo-defense.md](demo-defense.md).

---

## Recipe 5: Health check before thesis demo

```bash
codegraph doctor
codegraph status
codegraph stats
```

Fix any `graph_index` or `gds_plugin` failures before live demo.

---

## Recipe 6: JSON trace for debugging

```bash
codegraph query "your task" --trace 2>/dev/null | jq '.seeds, .top_results[:3]'
```

---

## Recipe 7: Dead code audit (CLI only)

```bash
codegraph analyze dead-code
```

Not available over MCP. Expect false positives on framework entrypoints.

---

## Recipe 8: SWE-bench pilot (5 issues)

```bash
pip install -e ".[bench]"
python -m evaluation.swe_bench_runner \
  --cache-dir .codegraph_cache \
  --output evaluation/results/pilot_$(date +%Y%m%d) \
  --limit 5 \
  --ablation baseline
```

Inspect `summary.json` in output dir.

---

## Recipe 9: Compare benchmark runs

```bash
python -m evaluation.compare_runs \
  evaluation/results/iteration_2_full/summary.json \
  evaluation/results/iteration_3_full/summary.json
```

(Adjust paths to actual run folders.)

---

## Recipe 10: Incremental dev loop

```bash
codegraph watch
# edit Python files; graph updates per save
codegraph query "your current task" --compact
```

After large git operations, prefer `codegraph rebuild`.

---

## Anti-recipes (do not)

- Guess file paths without `get_relevant_context`
- Expect MCP `find_dead_code` — it does not exist (DEC-007)
- Use `codegraph doctor --reset` — **not implemented**; use `codegraph rebuild` (clears via `clear_database`)
