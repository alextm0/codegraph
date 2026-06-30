# Presentation Slides 1-5 Design Spec

## Overview
This specification details the layout, on-slide text, and speaker notes for the first 5 slides of the CodeGraph thesis defense presentation. The design adheres strictly to a clean, academic Beamer style, ensuring high contrast, minimal text, and diagram-centric technical explanations. The primary goal is to provide enough visual and textual anchors to support a fast, confident speech without overwhelming the audience.

## Global Design Rules
- **Tone:** Academic, clear, and defense-ready.
- **Pacing:** Each slide is designed to be scanned in under 5 seconds and presented in 30-45 seconds.
- **Visuals:** Diagram-first technical slides; text is limited to 2-3 short support bullets per slide.
- **Layout:** Standard academic header/footer, generous whitespace, and left-aligned text for readability.

---

## Slide 1: Title
**Top takeaway sentence:** CodeGraph is a deterministic repository-level retrieval system for AI coding agents.
**Suggested layout:** Minimalist academic title page: centered title block, presenter info, affiliation, and supervisor directly below, with generous white space and no clutter. 
**On-slide content:**
- Title: CodeGraph: Repository-Level Structural Retrieval for AI Coding Agents via Personalized PageRank
- Presenter: Toma Alexandru-Mihai
- Supervisor: Lect. PhD. Arthur Molnar
- Babeș-Bolyai University
**Callout content:** [No callout needed]
**Speaker guidance:**
"Good morning, committee members. Today I am defending my thesis on CodeGraph, a deterministic, graph-based retrieval system that helps AI coding agents reliably navigate and understand large repositories without relying solely on text search."
**Diagram placeholder:** [No diagram needed]
**Transition to next slide:** "I will begin by outlining the structure of today’s presentation."

---

## Slide 2: Outline
**Top takeaway sentence:** The presentation will cover the core problem, our graph-based approach, the system architecture, empirical results, and a live demonstration.
**Suggested layout:** Numbered outline page with clear vertical spacing, items 1 to 5 stacked on the left, generous whitespace.
**On-slide content:**
1. Motivation and Problem
2. Why Code is a Graph
3. System Architecture
4. Empirical Evaluation
5. Conclusions and Demo
**Callout content:** [No callout needed]
**Speaker guidance:**
"Our roadmap today starts with the retrieval bottleneck facing modern AI agents. I will explain why code should be treated as a graph, introduce the CodeGraph architecture, discuss our evaluation on SWE-bench Lite, and conclude with a live system demonstration."
**Diagram placeholder:** [No diagram needed]
**Transition to next slide:** "Let's start by looking at why coding agents struggle to find what they need."

---

## Slide 3: The Retrieval Bottleneck
**Top takeaway sentence:** Pure text similarity fails because bug reports use abstract language while code uses specific structural identifiers.
**Suggested layout:** Title on top, left column with 2 to 3 short bullets, right side dominated by the vocabulary-gap diagram.
**On-slide content:**
- Issue reports use abstract natural language.
- Source code uses specific structural identifiers.
- Pure text embeddings fail to bridge this vocabulary gap.
**Callout content:** The Vocabulary Gap: Semantic intent does not match structural reality.
**Speaker guidance:**
"The main problem facing AI agents is the vocabulary gap. A user might write a bug report saying 'fix permissions logic,' but the actual code lives in a file named `global_settings.py`. Text embeddings fail here because they look for semantic overlap rather than structural meaning."
**Diagram placeholder:** [Insert diagram placeholder: left box with issue text "fix permissions logic", right box with target file "global_settings.py", dashed broken connection labeled "Vocabulary Gap"]
**Transition to next slide:** "To solve this, we must rethink how we represent the codebase itself."

---

## Slide 4: Rethinking Code as a Connected Graph
**Top takeaway sentence:** Codebases are highly interconnected systems linked by calls, imports, containment, and inheritance.
**Suggested layout:** Diagram-first, with the visual centered or dominant, and only a few support bullets on the side or bottom.
**On-slide content:**
- Codebases are not flat bags of text files.
- Relevant context is structurally close but textually distant.
- Key relationships: imports, calls, containment, and inheritance.
**Callout content:** Code is a connected system, not a bag of files.
**Speaker guidance:**
"We cannot treat a repository as a flat bag of text. Code is an interconnected system. The files that an agent needs to read might not share any keywords with the user's prompt, but they are structurally linked through imports, function calls, and inheritance."
**Diagram placeholder:** [Insert diagram placeholder: small code graph with nodes for file, class, function, and method, connected by IMPORTS, CALLS, CONTAINS, and INHERITS edges, with a structurally relevant neighborhood highlighted]
**Transition to next slide:** "Building on this principle, we designed the CodeGraph system."

---

## Slide 5: CodeGraph System Overview
**Top takeaway sentence:** CodeGraph indexes the repository into a static graph and retrieves context using deterministic Personalized PageRank.
**Suggested layout:** Academic architecture slide: title on top, large central diagram spanning the width, minimal support bullets below, one compact callout emphasizing retrieval properties.
**On-slide content:**
- Indexing Phase: Translates source code into a static dependency graph.
- Retrieval Phase: Uses lexical seeds and Personalized PageRank.
- Core Properties: Deterministic, low-latency, and reproducible.
**Callout content:** Zero LLMs in the retrieval loop.
**Speaker guidance:**
"This is the complete CodeGraph pipeline. First, the offline indexing phase parses source code into a static Neo4j dependency graph. Then, the online retrieval phase selects lexical entry points and uses Personalized PageRank to rank the structurally related code. The entire loop is deterministic and fast, with no LLMs involved in the ranking process."
**Diagram placeholder:** [Insert diagram placeholder: two-phase pipeline, Indexing Phase on the left with Raw Source Code -> Tree-sitter Parser -> AST -> Graph Builder -> Neo4j Graph, Retrieval Phase on the right with Task Description -> Seed Selector -> PPR Ranker -> Ranked Context -> AI Agent]
**Transition to next slide:** [End of slide 5]
