# Thesis Structure and Formatting

## Chapter map

| Ch | Focus | Length | Opening must include |
|----|-------|--------|----------------------|
| 1 | Introduction | 6–8 pp | Motivation, problem, example, contributions, outline |
| 2 | Background | 8–10 pp | What techniques ARE (survey) |
| 3 | Methodology | 10–12 pp | HOW configured (seeds, PPR, IDF) |
| 4 | Implementation | 8–10 pp | Code architecture, engineering trade-offs |
| 5 | Evaluation | 10–12 pp | SWE-bench Lite, metrics, ablations |
| 6 | Discussion | 6–8 pp | Interpretation, failure modes, validity |
| 7 | Conclusion | 4–6 pp | Contribution restatement, future work |

## Section opening (required)

Every major section/subsection:

1. **Challenge** — What problem or question?
2. **Approach** — How this section answers it.
3. **Structure link** — Relation to prior/next building blocks.

## Technical explanation pattern

1. Motivation (practical limitation)
2. Concrete example (mental model)
3. Formalization (minimal notation)
4. Mechanism (ordered steps)
5. Limitations (trade-offs, failure modes)

## Figures, tables, math

- Number hierarchically (Figure 3.1). Reference in text **before** the float.
- Captions self-contained for skimmers.
- Math in prose: "We denote the code graph by $G = (V, E)$" then define symbols immediately.
- Citations: numbered `[1]` style; group related work thematically in Ch.2.

## LaTeX conventions

- List introductions: `\noindent` before itemize/enumerate lead-in sentence.
- Cross-refs: `\cref{...}` with matching `\label{...}`.
- Verify new citations exist in `references.bib`.
