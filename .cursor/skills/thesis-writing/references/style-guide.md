# Thesis Writing Style Guide

## Voice and Tone

- **Person:** Use "we" for methods and results; use "this thesis / this chapter / this section" for structure. Avoid "I" except in short reflective passages.
- **Formality:** Professional, formal, explanatory. Avoid blog-style conversational openings like "Consider a scenario…", "Let's look at…", or "You might be wondering…".
- **Avoid instructional tone:** Do not use "We will show you how to…" or "You will learn that…". Instead, describe what the system does or what the chapter presents.
- **Verbs:** Use neutral and precise verbs such as "shows," "suggests," "indicates," "addresses," and "separates." Avoid marketing language or emotional flourishes.
- **Hedging:** Use appropriate hedging like "This result suggests…" or "One plausible explanation is…". Never overclaim.

## Punctuation (mandatory)

- **No em dashes:** Replace `---` / `—` with colons (definitions), commas (appositives), or parentheses.
- **No decorative quotes** on established technical terms (reachability, probability dilution, Seed-First).

## Core Principles

1. **Clarity first:** Write for an informed peer unfamiliar with this specific project. Define technical terms on first use *in this chapter*.
2. **Problem-solution framing:** Introduce the technical problem first, then how the approach solves it.
3. **Show, don't just tell:** Abstract concepts need example, diagram, or step-by-step walkthrough.
4. **Intuition first, formalism second:** motivation → example → definition → details → limitations.
5. **One idea per paragraph:** 4–8 sentences, one topic sentence.
6. **Signposting:** "In this section, we…", "Next, we show that…", "As shown above…".
7. **Manage phrase repetition:** Keep core terms fixed (Personalized PageRank); vary descriptive phrases (relevant code → pertinent entities).
8. **Abstract before concrete** for problem statements; concrete examples only clarify.
9. **No vocabulary decoration:** "uses" not "leverages"; "separates" not "division of labor".

## Cross-Chapter Consistency

- **Reference, don't re-explain:** "As established in Chapter 2…" instead of a fresh BM25 tutorial.
- **Chapter roles:** Ch.2 background (what it IS); Ch.3 methodology (HOW configured); Ch.4 implementation (code architecture); Ch.5 evaluation; Ch.6 discussion; Ch.7 conclusion.
- **Metrics:** State each headline number once per chapter; do not repeat +32pp / 74% R@10 in every section.

## Sentence and Paragraph Style

- **Length:** Under 25–30 words; split at the second core idea.
- **Active voice:** "We construct a code graph…" not "A code graph is constructed…".
- **Transitions:** However, In contrast, As a result, Consequently, In summary.
- **Banned qualifiers:** very, quite, somewhat, significantly (when paired with already-cited data), substantially, clearly, basically.
- **Topic sentences:** First sentence states the paragraph claim.

## Empirical grounding

- Replace "very few" with counts and ranges (e.g., 15/300 instances, ranks 6–10).
- Every design choice in Ch.3–5 should tie to ablation or benchmark evidence when available.
