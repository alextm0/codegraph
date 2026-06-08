# TikZ & Illustration Reference Guide

Use this guide when proposing, reviewing, or generating TikZ code and LaTeX tables for the CodeGraph thesis. The goals are minimalism, consistency, clean layout, and error-free compilation.

---

## 1. Node Positioning & Layout (Pain Point A)

To keep diagrams neat and mathematically consistent, follow these layout rules:

### A. Relative Positioning
* **Always** use the `positioning` library.
* **Never** use absolute coordinates like `(1, 2)` or `at (x, y)` for core nodes.
* Position nodes relative to others using `right=of`, `left=of`, `below=of`, `above=of`, `below right=of`, etc.
* Set standard spacing at the top of the `tikzpicture` options via:
  ```latex
  \begin{tikzpicture}[node distance=0.8cm and 1.2cm, ...]
  ```
  *(where `0.8cm` is vertical spacing and `1.2cm` is horizontal spacing).*

### B. Routing and Junctions via `calc`
* For alignment coordinates or junctions where arrows bend, use coordinate calculations:
  * Find the midpoint between two nodes:
    ```latex
    \coordinate (mid) at ($(nodeA.east)!0.5!(nodeB.west)$);
    ```
  * Align a point horizontally with one node and vertically with another:
    ```latex
    \coordinate (p) at (nodeA.east |- nodeB.north);
    ```

### C. Consistently Sized Nodes
* Specify `minimum width` and `minimum height` for similar node types so they form a balanced layout. E.g.,
  ```latex
  cgstage/.style={..., minimum width=2.5cm, minimum height=1.3cm}
  ```

---

## 2. Conceptual Mapping & Style Palette (Pain Point B)

All diagrams must align with the `Lattice` visual design system defined in [cg-visuals.sty](file:///Users/alexandrutoma/dev/codegraph/thesis/cg-visuals.sty):

### A. Stage Pipelines
* Sequential stages must use the `cgstage` styles with specific border colors:
  * Stage 1 (Parsing): `draw=latticeblue`
  * Stage 2 (Graph Build): `draw=latticegreen`
  * Stage 3 & 4 (Retrieval/Online): `draw=latticeorange`
  * Stage 5 (Context Delivery): `draw=latticeblue!70!black`
* Stage numbers must be marked using `cgbadge` above the stage nodes.

### B. Graph representation Diagrams
* Entity nodes must use these predefined styles:
  * File nodes: `cgnodefile` (Blue border, ttfamily)
  * Class nodes: `cgnodeclass` (Green border, ttfamily)
  * Function/Method nodes: `cgnodefunc` (Orange border, ttfamily)
* Edge styles:
  * Structural imports/contains: `cgstructarr`
  * Call/dependency paths: `cgstructarrred` (dashed, red)
  * Layout boundaries/panels: `cgpanel` or `cgstructpanel` (placed on the `background` layer).

---

## 3. LaTeX Integration & Page Fit (Pain Point C)

To ensure the diagram compiles correctly and fits nicely on the page:

### A. Prevent Layout Overflows
* **Mandatory**: Wrap every `tikzpicture` inside an `adjustbox` centering environment:
  ```latex
  \begin{figure}[H]
      \centering
      \begin{adjustbox}{max width=\textwidth,center}
      \begin{tikzpicture}[...]
          ...
      \end{tikzpicture}
      \end{adjustbox}
      \caption{Self-contained caption explaining the illustration.}
      \label{fig:label-name}
  \end{figure}
  ```
* For smaller diagrams, scale down using `max width=0.85\linewidth` or similar percentages to keep the layout proportional.

### B. Font Management
* All labels inside nodes must use relative LaTeX font sizes (`\small`, `\footnotesize`, `\tiny`) rather than absolute pt values. E.g., `font=\small\bfseries`.
* Use `align=center` and `text width` on nodes that contain multi-line text to allow auto-wrapping.

### C. Compile Safety
* Ensure all opening braces/brackets have matching closing braces/brackets (especially in path operations like `\draw`).
* Terminate all TikZ commands with a semicolon `;`.
