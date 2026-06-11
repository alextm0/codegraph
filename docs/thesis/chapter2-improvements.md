# Chapter 2 improvements backlog

Planned prose edits for [`thesis/chapters/chapter2_background_related_work.tex`](../../thesis/chapters/chapter2_background_related_work.tex). Add entries here as we identify them; apply all changes in one pass when the list is complete.

**Status:** 7 applied · 0 pending

---

## 1. Chapter introduction

**Location:** `\chapter{Background and Related Work}` — opening paragraphs (line 7)

**Status:** applied

### Before

```tex
This chapter builds the conceptual vocabulary needed to understand CodeGraph. Structural code retrieval requires three enabling technologies: a parser that converts source files into typed syntax trees, a graph database that stores and traverses the resulting dependency structure, and a ranking algorithm that propagates relevance from query-matched seeds to structurally connected entities. With these foundations in place, the chapter surveys the retrieval problem that motivates this thesis, contrasts three methodological families (sparse, dense, and graph-based), and examines five concrete graph-based systems to identify the research gaps that CodeGraph addresses.
```

### After

```tex
This chapter provides the technical and methodological background needed to situate CodeGraph within the broader landscape of repository-level code retrieval.

Building on these foundations, the chapter defines the retrieval problem addressed in this thesis, compares three major approaches to code retrieval, sparse, dense, and graph-based, and reviews five representative graph-based systems to identify the limitations that motivate CodeGraph.
```

**Notes:**

- Split into two paragraphs; roadmap only—no enumeration of the three core technologies here (moved to §2.1).
- “conceptual vocabulary” → situating CodeGraph in repository-level retrieval; “surveys … research gaps” → “defines … limitations that motivate”.

---

## 2. §2.1 Background introduction

**Location:** `\section{Background}` — opening paragraphs (line 14)

**Status:** applied

### Before

```tex
A structural retrieval system needs three capabilities: it must parse source files into typed entities, store and traverse the resulting dependency structure efficiently, and propagate relevance from query-matched starting points through the graph. This section introduces the three technologies that provide these capabilities in CodeGraph.
```

### After

```tex
A structural retrieval system must transform raw source code into a machine-usable representation, organize the resulting entities and relations in a form that supports efficient traversal, and rank the retrieved context by structural relevance.

In CodeGraph, these requirements are addressed through three core technologies: Tree-sitter for parsing, Neo4j for graph storage and traversal, and Personalized PageRank for relevance propagation.
```

**Notes:**

- Reframes capabilities as representation → organization → ranking; names the three technologies explicitly instead of deferring to subsections.

---

## 3. §2.1.1 Tree-sitter and Static Analysis (full subsection + Figure 2.1 caption)

**Location:** `\subsection{Tree-sitter and Static Analysis}` through `\caption{...}` for `fig:ast-to-graph` (lines 19–33)

**Status:** applied

### Before

```tex
Source code structure can be extracted through static analysis, which examines source text without program execution. The goal of this stage is to produce a structured representation of each source file that captures code units and their relationships, without requiring the code to be executed.

CodeGraph uses Tree-sitter~\cite{treesitter} as its parsing engine. Unlike traditional compiler-based parsers, Tree-sitter is designed around three properties that make it suitable for developer tooling:
\begin{itemize}
    \item \textbf{General:} It supports a wide range of programming languages through a unified grammar system.
    \item \textbf{Robust:} It can parse syntactically incomplete or erroneous code, which is common in active development environments.
    \item \textbf{Fast:} It builds an initial concrete syntax tree in sub-millisecond time and can incrementally update the tree as the file is modified.
\end{itemize}

\noindent These properties make Tree-sitter the parsing engine used by CodeGraph and several related systems surveyed in \cref{sec:graph-systems}. \Cref{fig:ast-to-graph} illustrates the transformation from raw source text through a syntax tree to the typed dependency graph used in later stages.

\begin{figure}[H]
    \centering
    \includegraphics[width=\textwidth]{assets/ast_to_graph.png}
    \caption{From source text to dependency graph. Tree-sitter converts each Python file into a concrete syntax tree; entity extraction then maps tree nodes to typed graph entities (File, Class, Method) connected by structural edges (CONTAINS, CALLS, IMPORTS, INHERITS\_FROM).}
    \label{fig:ast-to-graph}
\end{figure}
```

### After

```tex
Static analysis derives structural information from source code without executing the program~\cite{cousot1996abstract}. In CodeGraph, this stage produces a structured representation of each source file so that code entities and their relationships can be identified and carried forward into graph construction.

CodeGraph uses Tree-sitter~\cite{treesitter} as its parsing engine. Rather than depending on a full compiler pipeline, Tree-sitter parses source files into syntax trees that can be queried and transformed into higher-level program entities~\cite{comex2023}. This makes it well suited to repository analysis, where the goal is not to execute code, but to recover structure in a form that later stages can store, traverse, and rank.

Tree-sitter is particularly suitable for this role for three reasons. First, it supports a wide range of programming languages through a unified grammar framework. Second, it remains useful even when code is incomplete or syntactically invalid, which is common in active development environments. Third, it supports efficient incremental parsing, allowing syntax trees to be updated as files change rather than rebuilt from scratch~\cite{treesitterdocs}. Together, these properties make it a practical foundation for developer-facing analysis tools and for structural retrieval systems such as CodeGraph.

\Cref{fig:ast-to-graph} illustrates this transformation. Tree-sitter first parses raw source text into a syntax tree, after which CodeGraph extracts typed entities and structural relations that populate the dependency graph used in later stages.

\begin{figure}[H]
    \centering
    \includegraphics[width=\textwidth]{assets/ast_to_graph.png}
    \caption{From source text to dependency graph. Tree-sitter parses each Python file into a syntax tree, from which CodeGraph extracts typed entities and structural relations.}
    \label{fig:ast-to-graph}
\end{figure}
```

**Notes:**

- Replaces the `itemize` list with numbered prose (First / Second / Third); drops the **“sub-millisecond time”** claim (too specific without a benchmark source).
- Drops the cross-ref to `\cref{sec:graph-systems}` in this subsection (survey still appears later in the chapter).
- Figure bridge moved to its own paragraph before the float; caption shortened (see former entry 4, now merged here).

**Citation placement (recommended):**

| Location | Key | Rationale |
|----------|-----|-----------|
| Sentence 1 (static analysis definition) | `\cite{cousot1996abstract}` | Cousot, *Abstract interpretation* — program information without execution |
| Sentence introducing Tree-sitter as engine | `\cite{treesitter}` | Existing project citation |
| Syntax trees → higher-level entities | `\cite{comex2023}` *(optional)* | COMEX — Tree-sitter-based code representations for analysis |
| Three reasons (language support, robustness, incremental parsing) | `\cite{treesitterdocs}` | Official docs / project description, not a research paper |
| Figure-bridge sentence on extraction | *(none)* or repeat `\cite{comex2023}` | Optional if COMEX not used on prior sentence |

**Bib entries to add** (in `thesis/references.bib` at apply time):

| Key | Source |
|-----|--------|
| `cousot1996abstract` | Cousot, P. (1996). *Abstract interpretation.* ACM Computing Surveys, 28(2), 324–328. https://doi.org/10.1145/234528.234740 |
| `treesitterdocs` | Tree-sitter. *Basic Parsing.* https://tree-sitter.github.io/tree-sitter/using-parsers/ |
| `comex2023` *(optional)* | arXiv:2307.04693 (COMEX) — use for entity/representation workflow, not Tree-sitter product claims |

Existing `treesitter` entry (project page) stays as-is.

---

## 4. §2.1.2 Graph Storage and Ranking with Neo4j GDS (merged Neo4j + PageRank)

**Location:** replaces `\subsection{Graph Databases and Neo4j}` and `\subsection{PageRank and Personalized PageRank}` (lines 40–52)

**Status:** applied

### Summary

Merged storage, GDS projection, PageRank, and PPR into one subsection titled **Graph Storage and Ranking with Neo4j GDS**. Updated §2.1 intro to mention Neo4j GDS. Added bib keys: `robinson2013graph`, `neo4j2024docs`, `neo4jgds2024catalog`, `neo4jgds2024pagerank`, `brin1998pagerank`, `jeh2003ppr`.

---

## 5. §2.2 introduction, §2.2.1, and §2.2.2 rewrites

**Location:** `\section{Code Retrieval for LLM Agents}` opening through `\subsection{Retrieval-Augmented Generation for Code}`

**Status:** applied

### Citations applied

| Subsection | Citation |
|------------|----------|
| §2.2 intro | none (roadmap) |
| §2.2.1 context-window paragraph | `\cite{gpt4,claude3}` |
| §2.2.1 asymmetric-cost paragraph | none |
| §2.2.2 RAG definition | `\cite{lewis2020rag}` |
| §2.2.2 retrieval bottleneck closing | `\cite{yang2024swebench}` |

---

## 6. §2.3 Graph-Based Code Retrieval Systems (full rewrite)

**Location:** `\section{Graph-Based Code Retrieval Systems}` — four subsections (RepoGraph, LocAgent, CodexGraph, LARGER); replaces GraphCoder and CodeGraphContext surveys

**Status:** applied

### Notes

- Kept `fig:khop-explosion` TikZ diagram and `fig:design-space` unchanged.
- Updated `tab:graph-systems` and Research Gaps text for four-system survey.
- Bib: updated `chen2025locagent`, `liu2024codexgraph` (NAACL 2025); added `hu2026larger`.
- Chapter intro: “five” → “four” representative systems.

---

## 7. §2.4 Research Gaps (full rewrite)

**Location:** `\section{Research Gaps}` prose; kept `tab:graph-systems` and `fig:design-space` unchanged

**Status:** applied

### Notes

- Four `\subsection{}` gaps replace `\paragraph{Gap N: ...}` blocks.
- Gap 1 uses LARGER (not GraphCoder) for consistency with §2.3.
- Citations: `chen2025locagent`, `liu2024codexgraph`, `hu2026larger`, `yang2024swebench`.

---

## Template for new entries

<!--
## N. Short title

**Location:** section / label / approximate line

**Status:** applied

### Before

```tex
...
```

### After

```tex
...
```

**Notes:** (optional)
-->
