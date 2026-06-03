# Refinement Examples

Concrete before/after patterns. For audited snippets from your thesis, see `thesis/internal/PLAYBOOK.md`.

## Openings: conversational → formal

**Before:** Consider a concrete scenario. An AI agent is asked to fix a SQL compilation error…

**After:** Code retrieval for LLM agents faces a fundamental challenge: identifying the structurally relevant subset of files from natural language task descriptions…

---

**Before:** This is the retrieval problem CodeGraph addresses…

**After:** CodeGraph addresses this challenge through a multi-stage retrieval pipeline that combines lexical and structural analysis…

## Cross-chapter: don't re-teach

**Before:** CodeGraph relies on three complementary techniques. Sparse lexical search uses…

**After:** As established in Chapter 2, sparse retrieval, graph-based methods, and ranking algorithms each address distinct aspects of code retrieval…

## Remove instructional / reimplementation tone

**Before:** Every design decision is described here in enough detail that a reader could reimplement the system…

**After:** Each design decision is presented with empirical justification and implementation detail.

## Simplify vocabulary

**Before:** The guiding insight is a division of labor…

**After:** The system separates lexical seed identification from structural propagation…

**Before:** Modern static analysis tools leverage incremental parsing libraries such as tree-sitter.

**After:** Modern static analysis tools use incremental parsing libraries such as tree-sitter.

## Metrics: vague → grounded

**Before:** Very few instances fall in the middle ranks.

**After:** Only 15 out of 300 instances (5%) fall in the middle ranks (ranks 6--10).

## Section opening (full pattern)

Code retrieval requires a structured representation of repository dependencies. This section introduces the semantic code graph that enables such retrieval. We define the node and edge types that support repository-level queries via the Model Context Protocol.
