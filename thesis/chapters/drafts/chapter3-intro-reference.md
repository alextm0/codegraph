# Chapter 3 Introduction: Approved Revisions

Save this file as: chapter3-intro-reference.md

## Approved Introduction Text

### Paragraph 1: Problem Statement (Abstract, Not Concrete Example)

**Replaces:** The "Consider a concrete scenario" opening with SQL compilation error example.

**Key changes:**
- Abstract problem statement instead of concrete scenario
- Formal academic tone, not conversational
- Establishes the retrieval challenge broadly

### Paragraph 2: Solution Approach (Proper Chapter 2 Reference)

**Replaces:** The paragraph that incorrectly referenced "Chapter 1" and re-explained what BM25/PPR are.

**Key changes:**
- Fixed "Chapter 1" → "Chapter 2"
- References Chapter 2 properly without re-explaining concepts
- Focuses on HOW CodeGraph uses these techniques, not WHAT they are
- "synthesizes" instead of "integrates" (avoids duplicating Chapter 2 language)

### Paragraph 3: Chapter Scope (Design Methodology Focus)

**Replaces:** The paragraph using "division of labor" and "reader could reimplement."

**Key changes:**
- "division of labor" → "separates" (simpler, clearer)
- Removed "reader could reimplement the system from this chapter alone" (instructional tone)
- Added "Where Chapter 2 surveyed... this chapter details..." (explicit transition)
- "empirical justification and implementation detail" (shows rigor, not instruction)

### Paragraph 4: Chapter Structure Overview

**Replaces:** The original paragraph with inconsistent section numbering and varying verb choices.

**Key changes:**
- Consistent section numbering (3.X instead of 1.X)
- More formal verb choices: "shows" → "details", "covers" → "describes", "explains how" → "describes"
- Maintains clear roadmap structure

---

## Additional Changes Throughout Chapter

### 1. Fix All "??" Placeholder References

Replace with appropriate chapter/section references:
- Background concepts → "Chapter 2" or "Section 2.X"
- Evaluation results → "Chapter 4" or "Section 4.X"
- Within-chapter references → "Section 3.X"

**Example:**
- `?? surveyed the available building blocks` → `Chapter 2 established that...`
- `As shown in ??` → `As shown in Section 3.4` or `Chapter 4 demonstrates that...`

### 2. Remove Blog-Style Phrasing

**Remove or replace:**
- "Consider a scenario..."
- "This is where X comes in"
- "Let's look at..."
- "You might wonder..."
- "Here's how it works..."

**Replace with:**
- "X addresses this challenge through..."
- "The system separates..."
- "This section presents..."
- "A natural question is whether..."

### 3. Simplify Unnecessarily Complex Phrases

| Replace | With |
|---------|------|
| "division of labor" | "separates" or "separation" |
| "leverages" | "uses" |
| "endeavors to" | "attempts to" or direct verb |
| "facilitates" | "enables" or "supports" |
| "exhibits" | "shows" or "demonstrates" |

### 4. Vary Descriptive Phrases, Keep Technical Terms Consistent

**Keep consistent (core technical terms):**
- "Personalized PageRank" (or "PPR" after first definition)
- "seed selection"
- "code graph" (not alternating with "dependency graph" unless explicitly defined as equivalent)
- "retrieval pipeline"
- "entity matching"

**Vary for better flow (general descriptions):**
- "relevant code" can become "pertinent entities," "target files," "structurally connected code"
- "structural relationships" can become "dependency structure," "code organization," "entity connections"

### 5. Reference Chapter 2 Properly

**Wrong (re-explaining):**
```
In Chapter 2, we discussed that BM25 ranks documents by term frequency, 
and PPR computes node importance on graphs. CodeGraph uses both of these techniques.
```

**Correct (referencing):**
```
Chapter 2 established the theoretical foundations of BM25 and Personalized PageRank. 
This chapter details how CodeGraph synthesizes these techniques into a unified retrieval pipeline.
```

### 6. Section Opening Pattern

Every major section should follow this structure:

1. **Problem statement** — What challenge does this section address?
2. **Approach/solution** — How does this section solve it?
3. **Connection** — How does this relate to previous/next sections?

**Example:**
```
Section 3.2 addresses the challenge of entity extraction from Python source files. 
The system uses tree-sitter to parse AST nodes and extract qualified names. 
This extraction feeds directly into the graph building phase (Section 3.3), 
enabling dependency resolution.
```

---

## Checklist for Chapter-Wide Revision

- [ ] All "??" placeholders replaced with proper chapter/section references
- [ ] No conversational openings ("Consider...", "Let's...")
- [ ] No instructional tone ("we will show you...", "you will learn...")
- [ ] Chapter 2 referenced, not re-explained
- [ ] "Division of labor" and similar complex phrases simplified
- [ ] Core technical terms consistent throughout
- [ ] Descriptive phrases varied to avoid repetition
- [ ] Every section opens with problem-solution-connection pattern
- [ ] All figures referenced in text before they appear
- [ ] Figure captions are self-contained
- [ ] No exact phrase duplication from Chapter 2
