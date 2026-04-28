# COMPREHENSIVE VISUAL REDESIGN PROMPT
## Chapter 3: Design Methodology — Figures & Tables

> **Usage**: Use this prompt with a designer, a design-tool AI (Figma AI, Adobe Firefly, etc.),
> or as self-instructions when recreating visuals from scratch.
> All specifications are binding unless explicitly overridden.

---

## 1. OBJECTIVE

Redesign **all diagrams, flowcharts, and tables** in Chapter 3 (Design Methodology) to create
a **professional, consistent, publication-ready visual system** suitable for an academic
computer science thesis.

Every figure and table must feel like it belongs to the same design family — same palette,
same typography, same spatial rhythm.

---

## 2. GLOBAL DESIGN PRINCIPLES

### 2.1 Aesthetic Direction
| Attribute | Requirement |
|---|---|
| Style | Clean, minimal, professional academic |
| Consistency | All figures share the same visual language |
| Readability | Optimized for print (300 DPI) and screen |
| Accessibility | Colorblind-safe palette, WCAG contrast ratios |
| Hierarchy | Information importance must be visually obvious |

### 2.2 Typography Standards

| Role | Font | Size | Weight |
|---|---|---|---|
| Body text in figures | Sans-serif (Inter, Arial, Helvetica) | 10–12pt | Regular |
| Labels / annotations | Same sans-serif | 9–10pt | Medium |
| Code / complexity notation | Monospace (Fira Code, Courier New) | 9pt | Regular |

> ⛔ Never use: decorative fonts · all-caps body text · font size below 8pt

### 2.3 Color Palette (Colorblind-Safe)

| Role | Hex | Usage |
|---|---|---|
| Primary accent | `#2563EB` | Main elements, arrows, emphasis |
| Secondary accent | `#059669` | Success states, positive paths |
| Tertiary / Warning high | `#DC2626` | Warnings, drops, negative paths |
| Warning mid | `#F59E0B` | Highlights, intermediate states |
| Neutral dark | `#1F2937` | Text, borders |
| Neutral light | `#F3F4F6` | Backgrounds, containers |

### 2.4 Spacing & Layout Rules

- **Margins**: ≥ 10 mm around all figures
- **Padding inside boxes**: 8–12 px
- **Line spacing**: 1.2–1.5 for multi-line text
- **Spacing grid**: Use 4 px base unit → steps of 4 / 8 / 12 / 16 / 20 px only
- **Alignment**: Grid-align all related elements precisely
- **White space**: Use generously — do not pack elements

### 2.5 Global Shape Conventions

- Box corner radius: **8 px** (default) or **4 px** (compact/code elements) — pick **one** and stick to it
- Arrowheads: Consistent filled triangle, 10–12 px
- Drop shadows: `0 4px 6px rgba(0,0,0,0.05)` — subtle, not decorative

---

## 3. FIGURE SPECIFICATIONS

### FIGURE 1.1 — Five-Stage Pipeline Diagram

**Problem to fix**: Cluttered stage boundaries, timing hard to read, unclear Offline/Online split.

**Target design**:

```
Layout       : Horizontal left-to-right flow
Structure    : Two visual sections (Offline / Online) with a clear separator
               Five sequential stage boxes connected by arrows
               Data type annotations + timing info per stage
```

**Stage boxes**
- Shape: Rounded rectangle, minimum 140 × 80 px
- Stage number: Circle badge 24 px, positioned top-left
- Stage title: 11pt bold, `#1F2937`
- Example data (e.g. "847 files, 14 203 entities"): 9pt regular, `#4B5563`
- Timing label: 10pt bold, `#DC2626` (must stand out), placed top-right or bottom-right

**Sections**
- Offline section background: `#EFF6FF` (light blue)
- Online section background: `#F0FDF4` (light green)
- Section label: 12pt bold, positioned above the section

**Arrows**: 3 px solid `#2563EB`, subtle drop shadow

**Data type labels**: 9pt italic, `#6B7280`

**Total timing**: 14pt bold, prominent, displayed outside/below the pipeline

**Grid**: 20 px alignment grid

---

### FIGURE 1.2 — Three-Option Comparison Chart

**Problem to fix**: Unclear hierarchy, hard to compare options at a glance.

**Target design**:

```
Layout : Three equal-width card columns
         Comparison bar chart below cards
```

**Per card**
- Size: 180 × 220 px · Border: 2px solid `#E5E7EB` · Border-radius: 8 px · Padding: 16 px

**Header badge (40 px circle)**
| Option | Color | Meaning |
|---|---|---|
| Option 1 | `#DC2626` (red) | Poor choice |
| Option 2 | `#059669` (green) | **Our choice — highlight this** |
| Option 3 | `#F59E0B` (amber) | Acceptable |

**"Our Choice" indicator (Option 2 card)**
- Checkmark icon (16 px) in top-right corner
- Border: 3 px, `#059669`
- Subtle green shadow/glow

**Metrics section (three rows per card)**
- Rows: Graph Size / PPR Speed / Recall
- Label: 9pt regular, `#6B7280` | Value: 12pt bold, `#1F2937` | Units: 9pt, `#9CA3AF`

**Comparison bar chart (below cards)**
- Three grouped bars: Graph Size / PPR Speed / Retrieval Quality
- Y-axis: Logarithmic for Graph Size, linear for others
- Bar colors match option badge colors

---

### FIGURE 1.3 — Decision Tree (Call Resolution)

**Problem to fix**: Appears linear; decision paths hard to follow.

**Target design**:

```
Layout : Top-to-bottom flowchart
         Decision diamonds + action rectangles
```

**Node types**
| Node | Shape | Size | Background | Text color |
|---|---|---|---|---|
| Start | Rounded rect | 160 × 50 px | `#2563EB` | White |
| Decision | Diamond | 140 × 80 px | `#F59E0B` | `#1F2937` |
| CREATE EDGE | Rectangle | 140 × 50 px | `#059669` | White |
| DROP | Rectangle | 140 × 50 px | `#DC2626` | White |

**Connectors**
- YES path: 3 px solid `#059669`, label "YES" in 9pt bold
- NO path: 3 px solid `#DC2626`, label "NO" in 9pt bold
- Arrowheads: 10 px filled triangles

**Decision text**: 10pt regular, `#1F2937`, centered, ≤ 2 lines
**Action text**: 10pt bold, white, centered

**Spacing**: 40 px vertical gap between nodes; branches offset 100 px from center

**Design Principle Callout (bottom of figure)**
- Background: `#FFFBEB` · Border: 1px `#FDE68A`
- Icon: Lightbulb (16 px), left margin
- Text: 9pt italic, `#92400E`
- Message: *"False edges are toxic to PPR. Missing edges are benign."*

---

### FIGURE 1.4 — Code-to-Graph Transformation

**Problem to fix**: Mapping between code lines and graph entities is unclear.

**Target design**:

```
Layout : Three-column (35% | 30% | 35%) with bezier connectors
```

**Column 1 — Source Code**
- Background: `#F9FAFB` · Border: 1px `#E5E7EB` · Border-radius: 4 px
- Font: 9pt monospace, `#1F2937`
- Line number gutter: 30 px, right-aligned, 8pt, `#9CA3AF`

Syntax highlighting:
| Token | Color |
|---|---|
| Keywords (`from`, `class`, `def`) | `#7C3AED` |
| Strings | `#059669` |
| Functions | `#2563EB` |
| Comments | `#6B7280` |

**Column 2 — Extracted Entities (center)**
Entity boxes: 120 × 40 px rounded rects, color-coded by type:
| Type | Background |
|---|---|
| File | `#DBEAFE` |
| Class | `#D1FAE5` |
| Method | `#FED7AA` |
| Import | `#E0E7FF` |
| Call | `#FEE2E2` |

- Text: 9pt medium, `#1F2937` · Entity-type icon: 14 px, left margin

**Connecting arrows (Col 1 → Col 2)**
- Style: Curved bezier, 2 px, color matches entity type
- Label: line number in 8pt at midpoint

**Column 3 — Graph Edges**
- Edge type label: 10pt bold, `#1F2937`
- Format: `source ──[EDGE_TYPE]──> target`

Edge line styles:
| Edge | Style |
|---|---|
| CONTAINS | Solid, `#2563EB` |
| CALLS | Dashed, `#DC2626` |
| IMPORTS | Dotted, `#059669` |

**Outer container**: White bg · 2px border `#E5E7EB` · 20 px padding · shadow `0 4px 6px rgba(0,0,0,0.05)`

---

### FIGURE 1.5 — Property Graph Schema

**Problem to fix**: Node types unclear; edge relationships hard to parse.

**Target design**:

```
Layout : Node-link diagram with example fragment + legend box
```

**Node types (4)**
| Type | Background | Border |
|---|---|---|
| File | `#DBEAFE` | 2px `#1E40AF` |
| Class | `#D1FAE5` | 2px `#065F46` |
| Function | `#FED7AA` | 2px `#C2410C` |
| Method | `#FECACA` | 2px `#991B1B` |

All nodes: 100 × 50 px rounded rectangles · Name: 10pt bold, centered · Properties (if shown): 8pt, `#6B7280`

**Edge types (4)**
| Edge | Style | Thickness | Color | Shape |
|---|---|---|---|---|
| CONTAINS | Solid | 3 px | `#2563EB` | Straight |
| CALLS | Dashed | 3 px | `#DC2626` | Curved |
| IMPORTS | Dotted | 3 px | `#059669` | Straight |
| INHERITS | Dash-dot | 3 px | `#7C3AED` | Curved |

All arrowheads: 12 px filled triangles

**Example fragment (auth.py)**
- 6 nodes arranged hierarchically
- CONTAINS edges vertical (parent-child)
- CALLS / IMPORTS edges at angles
- Minimize edge crossings

**Legend box (top-right)**: 150 × 120 px · Background `#F9FAFB` · Border 1px `#E5E7EB`
- Lists: "Node Types (4):" and "Edge Types (4):" with colored samples

**Property infobox (near legend)**: 100 × 80 px · Background `#F3F4F6`
- Fields: `qualified_name`, `file_path`, `line_number`, `docstring` · 8pt font

---

### FIGURE 1.7 — Seed Selection Signal Flow

**Problem to fix**: Signal strength encoding unclear; merge process hard to follow.

**Target design**:

```
Layout : Multi-input funnel → single output
         Box sizes and arrow widths encode confidence/weight
```

**Input boxes (3 signals) — size proportional to weight**
| Signal | Size | Color | Weight Badge |
|---|---|---|---|
| Entity Match | 180 × 60 px | `#DC2626` (red) | **60%** |
| BM25 | 150 × 50 px | `#2563EB` (blue) | **30%** |
| Current File | 120 × 40 px | `#9CA3AF` (gray) | **10%** |

Badge: top-right corner, 14pt bold white

**Processing text inside each box**
- Entity Match: `"Graph Lookup + IDF Weight"`
- BM25: `"Compound Tokenizer (CamelCase)"`
- Current File: `"File Entity Lookup (all in file)"`

**Connecting arrows — width encodes weight**
- 60% signal → 6 px
- 30% signal → 3 px
- 10% signal → 1.5 px
- Label: weight value (0.6 / 0.3 / 0.1) in 10pt bold

**Merge box**
- Shape: Hexagon, 160 × 80 px · Background `#FEF3C7` · Border 2px `#F59E0B`
- Text: "Merge & Normalize" 11pt bold · Formula: `Σᵢ sᵢ = 1.0` 10pt monospace

**Output box**
- Shape: Rounded rect 200 × 60 px · Background `#FDBA74` · Border 3px `#EA580C`
- Text: "Personalization Vector s⃗" · 12pt bold white · Vector icon (↗) 20 px

**Worked example panel (bottom, full-width)**
- Background `#F0F9FF` · Border 1px `#BAE6FD` · Padding 16 px
- Title: "Worked Example" 11pt bold `#0C4A6E`
- Table columns: Signal type | Matches found (monospace) | Weight (right-aligned monospace)
- Sum row: Bold, 2px solid border-top `#0369A1`

---

### FIGURE 1.8 — Sequence Diagram (Agent–MCP Interaction)

**Problem to fix**: Timing unclear, message flow cluttered.

**Target design**:

```
Layout : Standard UML sequence diagram, vertical time axis
```

**Participants (3 lifelines)**
| Participant | Box color | Spacing |
|---|---|---|
| AI Agent | `#DBEAFE` | — |
| MCP Server | `#FEF3C7` | 250 px from previous |
| Neo4j + GDS | `#D1FAE5` | 250 px from previous |

Participant boxes: 140 × 50 px rounded · Lifelines: 2px dashed `#9CA3AF`

**Activation bars**: 20 px wide, semi-transparent participant color, 2px border

**Message arrows**
| Type | Style | Color | Arrowhead |
|---|---|---|---|
| Synchronous call | Solid 2px | `#2563EB` | Filled |
| Return | Dashed 1px | `#6B7280` | Open |

- Label above arrow: 9pt regular
- Content preview below arrow: 8pt monospace, `#4B5563`

**Processing boxes (floated right of activation bar)**
- Size: 180 px wide, auto-height · Background `#FEF3C7` · Border 1px `#FDE68A`
- Title: 9pt bold `#92400E` · Bullets: 8pt regular `#92400E`
- Timing: 8pt monospace, right-aligned, `#DC2626`

**Data preview tags** (inline with arrows)
- Background `#F3F4F6` · Border 1px `#D1D5DB` · Font 8pt monospace
- Examples: `[14523, 8821, ...]`, `auth/views.py (3.2K)`

**Step numbers** (left margin)
- 20 px circles, white number on `#2563EB`
- Align with first message of each interaction group

**Timing panel (right margin)**
- Cumulative ruler with markers at 35 ms / 147 ms / 200 ms
- Color: Green (fast) · Amber (acceptable) · Red (at threshold)
- Total time: 14pt bold badge at bottom

**Optional call**: Dashed border around message, "optional" label in 8pt italic `#6B7280`

---

## 4. TABLE SPECIFICATIONS

### 4.1 Global Table Standards

**Typography**
| Element | Font | Size | Weight | Color |
|---|---|---|---|---|
| Header row | Sans-serif | 10pt | Bold | `#1F2937` on `#F3F4F6` |
| Body text | Sans-serif | 9pt | Regular | `#374151` |
| Complexity / code | Monospace | 10pt | Regular | `#DC2626` |

**Borders**
- Outer: 2px solid `#D1D5DB`
- Header bottom: 2px solid `#9CA3AF`
- Row separators: 1px solid `#E5E7EB`
- ⛔ No vertical borders between columns

**Cell spacing**: 8px vertical · 12px horizontal padding · min row height 36 px

**Alignment**: Text → left · Numbers → right · Mixed → left · Headers match column

**Row banding**: Even `#FFFFFF` · Odd `#F9FAFB`

---

### TABLE 1.1 — Computational Complexity

Columns and widths: `Stage (20%) | Phase (15%) | Dominant Operation (40%) | Complexity (25%)`

- **Phase column**: Badge style · "Offline" → `#FEF3C7` bg / `#92400E` text · "Online" → `#D1FAE5` bg / `#065F46` text · Border-radius 12 px · Padding 4 × 8 px
- **Complexity column**: Monospace 10pt `#DC2626` · Examples: `O(n·m)`, `O(|V|+|E|)`, `O(t·|E|)`

---

### TABLE 1.2 — Entity Types

Columns and widths: `Entity Type (18%) | Key Properties (22%) | Description (35%) | Qualified Name (25%)`

- **Entity Type icons** (16 px, left margin): File 📄 `#2563EB` · Class 🔷 `#059669` · Function 🔸 `#F59E0B` · Method 🔹 `#DC2626`
- **Qualified Name cell**: Background `#F3F4F6` · Left border 3px solid matching entity color · Padding 4 × 8 px · 9pt monospace italic

---

### TABLE 1.3 — Edge Types

Columns and widths: `Edge Type (20%) | Source → Target (25%) | Semantic Meaning (45%) | Base Wt. (10%)`

- **Edge Type column**: 60 px line sample inline with name
  - CONTAINS → solid 3px `#2563EB`
  - CALLS → dashed 3px `#DC2626`
  - IMPORTS → dotted 3px `#059669`
  - INHERITS_FROM → dash-dot 3px `#7C3AED`
- **Arrow in Source → Target**: Unicode `→`, 12pt, `#6B7280`
- **Example text in Semantic Meaning**: prefix "e.g., " 8pt italic `#6B7280` · value 9pt monospace `#1F2937`

---

### TABLE 1.4 — IDF Edge Weight by In-Degree

Columns and widths: `Target Entity (20%) | Example (18%) | In-degree (12%) | IDF Weight (12%) | Interpretation (38%)`

**Row color-coding by IDF weight**
| Weight range | Row background |
|---|---|
| > 0.40 | `#ECFDF5` (light green) |
| 0.20 – 0.40 | `#FFFBEB` (light yellow) |
| < 0.20 | `#FEF2F2` (light red) |

- **In-degree**: Bold · Color gradient `#059669` (low) → `#DC2626` (high)
- **IDF Weight**: Monospace · Always 2 decimal places · Color `#1F2937`
- **Interpretation**: Em-dash separator `—` · Color intensity mirrors weight value

---

### TABLE 1.5 — Recall Comparison (Uniform vs Weighted)

Columns and widths: `Iteration (15%) | Seed Quality (25%) | Weighted R (15%) | Uniform R (15%) | Δ (12%) | Zero-recall (18%)`

**Header**: Two-row merged header · Top row: "Restart Mode Comparison" centered

**Highlighting**
- Uniform R column: `#ECFDF5` background (winner column)
- Δ values: Positive → `+` prefix · `#059669` bold · Negative → `#DC2626`
- All percentage values: 1 decimal place (e.g. `42.0%`) · Monospace · Right-aligned
- Zero-recall count: 8pt `#6B7280`, in parentheses or separate sub-column

---

### TABLE 1.6 — MCP Server Tools

Columns and widths: `Tool (28%) | Parameters (32%) | Use Case (40%)`

- **Tool column**: 10pt monospace bold · Color `#2563EB` · Function-like format (e.g. `get_relevant_context`)
- **Parameters column**: Multi-line bulleted list · Indent 12 px · Required params bold · Optional params italic with `(optional)` suffix
- **Use Case column**: Multi-sentence OK · Line-height 1.4 · Key verbs bold
- **Primary tool row** (`get_relevant_context`): Left border 4px solid `#2563EB` · Background `#EFF6FF` · "PRIMARY" badge top-right
- Min row height: 48 px

---

## 5. CAPTION FORMATTING

### Figure captions
```
Position  : Below figure, centered
Font      : 10pt regular, #374151
Line-height: 1.4
Max width : 90% of figure width
Format    : "Figure X.Y: **[Title].** [Description — 2–3 sentences max]"
```

### Table captions
```
Position       : Above table, centered
Font           : 10pt regular, #374151
Format         : "Table X.Y: **[Title — 5–10 words]**"
Additional note: Below table, 9pt italic (if needed)
```

### Cross-references in captions
- Format: `see Section X.Y` or `as shown in Table X.Y`
- Style: `#2563EB` (hyperlink color in PDF)
- Never bold or italic

---

## 6. TECHNICAL SPECIFICATIONS

### Export format
| Asset | Format |
|---|---|
| Figures | PDF (embedded fonts) + SVG source |
| Tables | LaTeX (`booktabs`) or PDF |
| Style guide | PDF, 1-page |
| Source files | `.ai` / `.fig` / `.drawio` / `.tex` |

- Resolution: ≥ 300 DPI for any raster elements
- Color space: RGB for screen, CMYK if going to print
- Target file size: < 500 KB per figure

### Recommended tools
| Task | Recommended tools |
|---|---|
| Diagrams / flowcharts | draw.io · Lucidchart · Figma · Adobe Illustrator |
| Charts / graphs | Python (matplotlib / seaborn) · R (ggplot2) · D3.js |
| Tables | LaTeX + `booktabs` · Adobe InDesign |
| Sequence diagrams | PlantUML · Mermaid · draw.io |

### Accessibility requirements
- Alt text: 1–2 sentences for every figure
- Color contrast: ≥ 4.5:1 for text · ≥ 3:1 for UI elements
- Use patterns in addition to color (not as replacement)
- Text embedded in images: minimum 10pt, avoid where possible

---

## 7. FINAL CONSISTENCY CHECKLIST

Before marking any figure or table as "done", verify every item:

- [ ] Same color palette — no ad-hoc colors introduced
- [ ] Same font family — sans-serif + monospace only
- [ ] Consistent border-radius — 8 px (default) or 4 px (compact) — one, not both
- [ ] Consistent arrowhead style across all figures
- [ ] All tables have identical border treatment
- [ ] All captions follow the defined format exactly
- [ ] Spacing uses the 4 px grid exclusively
- [ ] All text is legible at 100% and 150% zoom
- [ ] Clear visual hierarchy in every figure (most important = largest / boldest)
- [ ] Zero pixelated elements — all vectors or ≥ 300 DPI rasters

---

## 8. DELIVERABLES SUMMARY

| # | Deliverable | Count | Format |
|---|---|---|---|
| 1 | Redesigned figures | 7 (1.1–1.8) | PDF + SVG per figure |
| 2 | Redesigned tables | 6 (1.1–1.6) | LaTeX source or PDF |
| 3 | Style guide | 1 page | PDF |
| 4 | Editable source files | All assets | `.ai` / `.fig` / `.drawio` / `.tex` |

---

*Generated for Alexandru Toma — Chapter 3 Visual Redesign, Undergraduate CS Thesis*
