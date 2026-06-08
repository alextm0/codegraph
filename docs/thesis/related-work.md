# Related work

Positioning CodeGraph for thesis writing and agent context. Not a literature review — see `thesis/chapters/chapter2_background_related_work.tex` for citations.

---

## vs embedding retrieval (RAG)

| Aspect | Embedding RAG | CodeGraph |
|--------|---------------|-----------|
| Similarity | Vector cosine | Graph distance (PPR) |
| Structure | Implicit in chunks | Explicit CALLS/IMPORTS |
| Hubs | Common in generic corpora | IDF down-weights high in-degree |
| Failure mode | Lexical lookalikes | Disconnected graph / bad seeds |

CodeGraph does **not** use code embeddings for ranking (by design).

---

## vs CodeGraphContext (CGC)

[CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) is the closest open-source cousin. Local reference docs: `docs/CodeGraphContext-Docs-From-Github/` (**inspiration only**).

| Dimension | CodeGraphContext | CodeGraph (this repo) |
|-----------|------------------|------------------------|
| Languages | Many (tree-sitter + SCIP option) | Python only |
| Storage | Kuzu, FalkorDB, Neo4j, etc. | Neo4j + GDS only |
| MCP tools | ~25 (index, search, analyze, …) | **2** (context + dependencies) |
| Primary query | Symbol search, relationship types | PPR task ranking |
| Bundles / portable graphs | `.cgc` bundles | Not implemented |
| Retrieval for agents | Multiple tools | `get_relevant_context` optimized for SWE-bench |

**When to borrow from CGC:** multi-language parser layout, deployment patterns, test ideas — always re-document in this repo.

**When not to copy:** MCP surface explosion, features we explicitly excluded.

---

## vs generic IDE codebase indexers

IDE indices (LSP, ctags) give symbols and references; CodeGraph adds **global ranking for a natural-language task** via PPR and benchmark-tuned seeds.

---

## Limitations (honest scope)

- Static Python only
- No runtime / dynamic dispatch
- File-level eval metric may undercount multi-file fixes
- Neo4j operational cost vs embedded DBs (CGC’s Kuzu path)

Roadmap: [../roadmap.md](../roadmap.md).
