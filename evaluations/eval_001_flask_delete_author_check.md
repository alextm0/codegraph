# Eval 001 — Flask: Delete Author Authorization

**Date:** 2026-03-03
**Query:** "Explain how the application ensures that only the author of a blog post can delete it, and trace all database interactions involved in this flow from the route handler to the actual SQL execution."
**Target codebase:** `tests/fixtures/flask/examples/tutorial/flaskr`
**Model used for answer:** Gemini 3 Flash (via Antigravity)
**Context source:** `eval_001_result.json` (MCP server output)

---

## Expected Context (ground truth)

| Entity | File | Why needed |
|---|---|---|
| `delete` | `blog.py:115` | Route handler — entry point |
| `get_post` | `blog.py:28` | Core author check (`check_author` / `g.user["id"]`) |
| `login_required` | `auth.py:18` | Ensures user is logged in before the route runs |
| `load_logged_in_user` | `auth.py:31` | Loads `g.user` from session via DB SELECT |
| `get_db` | `db.py:9` | DB access layer — returns SQLite connection |
| `db.py` (file) | `db.py` | Full SQLite setup context |

---

## Pipeline Output (ranked)

| Rank | Entity | Score | Verdict |
|---|---|---|---|
| 1 | `get_post` | 0.346 | ✅ Correct — authorization core |
| 2 | `blog.py` (whole file) | 0.318 | ✅ Redundant but harmless |
| 3 | `update` | 0.280 | ⚠️ Marginal — similar structure but not the target |
| 4 | `delete` | 0.262 | ✅ Present — but ranked below `update` (should be higher) |
| 5 | `validate_username` (user_auth) | 0.200 | ❌ Noise — wrong fixture |
| 6 | `get_db` | 0.165 | ✅ Correct |
| 7 | `clean_db` (conftest.py) | 0.165 | ❌ Noise — codegraph test infrastructure |
| 8 | `validators.py` (user_auth) | 0.160 | ❌ Noise — wrong fixture |
| 9 | `AuthService.register` (user_auth) | 0.145 | ❌ Noise — wrong fixture |
| 10 | `conftest.py` | 0.127 | ❌ Noise — codegraph test infrastructure |
| 11 | `auth.py` (whole file) | 0.112 | ✅ Correct — contains `login_required` + `load_logged_in_user` |
| 12 | `render_template` | 0.080 | ⚠️ Not needed |
| 13 | `flash` | 0.076 | ⚠️ Not needed |
| 14 | `abort` | 0.075 | ✅ Relevant — used in `get_post` to raise 403 |
| 15 | `db.py` (whole file) | 0.074 | ✅ Correct |

---

## Issues Found

### 1. Cross-fixture contamination (ranks 5, 7, 8, 9, 10)
**Severity: High**
Entities from the unrelated `user_auth` fixture and codegraph's own `conftest.py` bleed into results.
PPR mass is leaking across fixtures because the graph indexes all fixtures together.
The `user_auth` fixture loosely shares concepts (db, auth) but is completely irrelevant to the Flask query.

**Affected entities:**
- `validate_username`, `validators.py`, `AuthService.register` — from `user_auth`
- `clean_db`, `conftest.py` — from codegraph test infrastructure

### 2. `delete` ranked below `update` (0.262 vs 0.280)
**Severity: Medium**
The actual route being asked about (`delete`) scores lower than the structurally similar `update`.
Both call `get_post`, but the query is specifically about delete.
Seed selection is not differentiating strongly enough on the target function.

### 3. Whole-file results duplicate individual function results
**Severity: Low**
`blog.py` (rank 2) fully contains `get_post`, `update`, and `delete`, which are already returned individually.
This wastes tokens delivering the same code 2–3x.
Post-processing should suppress a whole-file entry when its key functions are already ranked above it.

---

## Overall Assessment

**Signal completeness: 8/10** — All four necessary entities are present in the output.
**Noise ratio: 5/15 results are irrelevant (~33%).**
**Answer quality from Gemini: Likely accurate** — the relevant signal dominates the top results; a capable model can ignore the noise.

---

## Suggested Fixes

| Fix | Target component |
|---|---|
| Scope graph per-codebase or penalize cross-fixture IDF | `graph_builder.py` / `post_processing.py` |
| Boost seed entity directly in PPR personalization vector | `seed_selection.py` |
| Deduplicate whole-file results when sub-functions already ranked | `post_processing.py` |
