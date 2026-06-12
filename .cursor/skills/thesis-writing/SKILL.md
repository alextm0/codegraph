---
name: thesis-writing
description: Refines CodeGraph thesis LaTeX prose in the author's academic voice; grounds technical claims in docs/ and DECISIONS.md before writing. Use when drafting or editing thesis chapters, reviewing Zotero annotations, tightening arguments, checking evaluation numbers, or structuring sections in thesis/.
---

# Thesis Writing (CodeGraph)

Refine thesis prose to match the **Transparent System** narrative: teach one idea per section, build bottom-up, ground claims in ablation data.

## Project documentation (mandatory — read before you write)

**Never guess** at architecture, defaults, MCP behavior, module names, or benchmark numbers. The repo’s **source of truth** is the tracked `docs/` tree, starting at [docs/README.md](../../../docs/README.md). Read the relevant pages **before** drafting or revising any technical claim; align thesis wording to what those files say.

| Thesis topic | Read first (in order) |
|--------------|------------------------|
| Any system / pipeline claim | `docs/concepts/architecture.md`, `docs/concepts/how-it-works.md` |
| Graph, edges, identity, PPR | `docs/concepts/graph-model.md`, `docs/concepts/retrieval-pipeline.md`, `docs/reference/config.md` |
| Parsing, CALLS/IMPORTS | `docs/concepts/parser.md`, `docs/concepts/call-resolution.md` |
| Implementation / modules | `docs/reference/module-map.md`, `docs/PROJECT_LAYOUT.md` |
| MCP, agent integration | `docs/reference/mcp.md`, `docs/MCP_TOOLS.md`, `AGENTS.md` |
| Evaluation, metrics, ablations | `docs/thesis/evaluation.md`, `docs/guides/evaluation-harness.md`, then `thesis/chapters/chapter5_evaluation_results.tex` |
| Related work / CGC comparison | `docs/thesis/related-work.md` |
| Binding design choices | `DECISIONS.md` (ACTIVE entries override memory or old thesis drafts) |

**Not authoritative:** `docs/CodeGraphContext-Docs-From-Github/` (inspiration only; gitignored vendored snapshot).

If prose conflicts with `docs/` or `DECISIONS.md`, **fix the thesis** (or flag a doc drift for the user). Do not invent APIs, tool counts, PPR defaults, or percentages. Root README marketing numbers are stale until verified against `docs/thesis/evaluation.md` and `evaluation/results/*/summary.json`.

**Living style memory:** read `thesis/internal/` before substantive edits (PLAYBOOK, PREFERENCES, TODO).

---

## Choose a mode

| User intent | Follow |
|-------------|--------|
| Full section review | [5-step workflow](#5-step-review-workflow-mandatory) + [revision output](#revision-output-format) |
| Light polish / single paragraph | Style pass only (steps 1, 4); skip visual proposals unless asked |
| New draft from bullets | Section opening pattern + [technical explanation pattern](references/structure-and-formatting.md) |
| Fact-check metrics | Read `docs/thesis/evaluation.md` + [factual-claims.md](references/factual-claims.md); cite `summary.json` if numbers change |
| Technical accuracy pass | Cross-check section against docs table above; note doc paths used in revision output |
| TikZ / table design | PREFERENCES.md + [Lattice visuals](#lattice-visuals) |

---

## Narrative (non-negotiable)

1. **Bottom-up:** prerequisites before the whole (parsing → graph → seeds → PPR → post-processing).
2. **One teaching goal per section:** state what the reader learns in the opening.
3. **Intuition order:** Motivation → Intuition → Example → Formalization → Details → Transition.
4. **Success trajectory:** frame engineering iterations as measured wins (+32pp over BM25, etc.) with numbers once per chapter.
5. **Cross-chapter:** reference prior definitions; do not re-teach (Ch.2 = what it is; Ch.3 = how we use it; Ch.4 = implementation).

---

## 5-step review workflow (mandatory)

For any multi-paragraph edit or chapter pass:

1. **Logical Flow Audit** — Map paragraph-by-paragraph logical progression (`P1 -> P2 -> P3`) of the section. Identify conceptual gaps, missing motivation, or premature conclusions before editing. Open matching `docs/` pages from the table above; flag any thesis line that contradicts them. Mark vague/dense phrasing, sentences >25 words, cognitive overload. Map Zotero comments to line ranges if provided.
2. **Rewrite for purpose** — Topic sentence first; subsection must have one clear teaching goal. Implement active voice, split long sentences, and use precise casing for technical terms.
3. **Visual & technical synthesis** — Every complex flow needs TikZ, listing, or table; propose concrete figure if missing. Check [tikz-guide.md](references/tikz-guide.md) for coordinate, styling, and scaling standards.
4. **Language pass** — Active *we*; strip weasel words; no quotes on established terms; no em dashes (use colon/comma/parens). See [style-guide.md](references/style-guide.md) and PLAYBOOK.md patterns.
5. **LaTeX sanity** — `\label`/`\cref`, list intros with `\noindent`, citations vs `references.bib`.

After a major pass, **suggest** (do not silently edit unless asked): CHANGELOG entry, new PLAYBOOK pattern if reusable.

---

## Revision output format

When returning edits, use:

```markdown
## Summary
[1–2 sentences: teaching goal + main structural change]

## Logical Flow Audit
* **Progress Map**: `P1 (Intent) -> P2 (Intent) -> P3 (Intent)`
* **Gaps/Transition Issues**: (Detailed analysis of flow and logical connections)

## Changes
### [subsection id or title]
**Issue:** …
**Before:** …
**After:** …
**Rationale:** (PLAYBOOK rule / style principle)

## Proposed visuals (if any)
- Figure/Table: [title] — [what it shows] — [where in section]

## Documentation consulted
- [paths to docs/ files read for this pass]

## Checklist
- [ ] Logical flow audit completed and progression mapped
- [ ] Claims match `docs/` + `DECISIONS.md` (list conflicts if any)
- [ ] Teaching goal stated in opening
- [ ] Bottom-up order
- [ ] Metrics grounded (no weasel words)
- [ ] No em dashes / no quoted technical terms
- [ ] Numbers match chapter 5 / summary.json
- [ ] TikZ/Tables conform to [tikz-guide.md](references/tikz-guide.md)
```

For long `.tex` excerpts, prefer **After** blocks only when the change is localized; otherwise give a patch-style rewrite of the paragraph.

---

## Style quick rules

| Do | Don't |
|----|-------|
| We construct / We evaluate | Passive "is constructed"; *leverages*, *utilizes* |
| Limited by context window | Strictly bounded; dramatically transformed |
| 32 percentage point improvement | Substantial/significant/very + number |
| reachability, Seed-First (no quotes) | "reachability", blog openers ("Consider a scenario…") |
| Reference Ch.2 for background | Re-explain BM25/PPR in Ch.4 |

**Key terms (use consistently):** Seed Extraction, Semantic Gap, Lexical-Structural Complementarity, Probability Dilution, Reachability Bottleneck.

---

## Lattice visuals

From `thesis/internal/PREFERENCES.md`:

- **Colors:** Blue `#2563EB` (core), Green `#059669` (success), Red `#DC2626` (failure), Orange `#F59E0B` (refinements).
- **TikZ:** 8pt rounded corners, `inner sep=10pt`, external stage badges (`xshift=-10pt, yshift=10pt`), 1.5pt blue main arrows.
- **Tables:** `tabularx` + `booktabs`, no vertical rules, no header hyphenation.

---

## Project paths

| Path | Use |
|------|-----|
| `docs/README.md` | **Doc hub — start here** for any technical lookup |
| `docs/concepts/`, `docs/reference/`, `docs/guides/` | Implementation truth (see table above) |
| `DECISIONS.md` | Binding design decisions |
| `thesis/chapters/*.tex` | Main prose |
| `thesis/internal/PLAYBOOK.md` | Proven before/after patterns |
| `thesis/internal/PREFERENCES.md` | Visual + punctuation mandates |
| `thesis/internal/CHANGELOG.md` | Suggest entries after major edits |
| `thesis/internal/TODO.md` | Pending section tasks |
| `docs/thesis/overview.md` | Research question ↔ code mapping |
| `docs/thesis/evaluation.md` | SWE-bench metrics & citation rules |

Combine PDF: `thesis/scripts/combine_thesis.py`

---

## Additional resources

- [style-guide.md](references/style-guide.md) — voice, paragraphs, hedging
- [structure-and-formatting.md](references/structure-and-formatting.md) — chapter map, section openings
- [examples.md](references/examples.md) — before/after snippets
- [factual-claims.md](references/factual-claims.md) — benchmark numbers agents may cite
