# Chapter 3 Visual Redesign — Quick Reference Card

## COLOR PALETTE

| Token | Hex | Use |
|---|---|---|
| Primary | `#2563EB` | Arrows, emphasis, links |
| Success | `#059669` | Positive paths, success |
| Danger | `#DC2626` | Warnings, drops, timing |
| Warning | `#F59E0B` | Highlights, intermediate |
| Text dark | `#1F2937` | Body text, borders |
| BG light | `#F3F4F6` | Containers, table headers |

---

## TYPOGRAPHY

| Role | Font | Size |
|---|---|---|
| Figure body | Inter / Arial | 10–12pt |
| Labels | Inter / Arial | 9–10pt |
| Code / O-notation | Fira Code / Courier New | 9pt |
| Min allowed | any | 8pt |

---

## SPACING GRID (4px base)

`4px · 8px · 12px · 16px · 20px`  
Figure margins: ≥ 10 mm · Cell padding: 8px × 12px

---

## BORDER RADIUS

- Default boxes: **8 px**
- Compact / code blocks: **4 px**
- Phase badges / pills: **12 px**

---

## ARROW STYLES (Figures)

| Context | Stroke | Color |
|---|---|---|
| Main flow | 3px solid | `#2563EB` |
| YES path | 3px solid | `#059669` |
| NO path | 3px solid | `#DC2626` |
| Weighted (heavy) | 6px solid | source color |
| Weighted (light) | 1.5px solid | source color |
| Return (sequence) | 1px dashed | `#6B7280` |

---

## TABLE BORDERS

- Outer: `2px solid #D1D5DB`
- Header bottom: `2px solid #9CA3AF`
- Row dividers: `1px solid #E5E7EB`
- ⛔ No vertical column borders

---

## NODE SIZE CHEAT SHEET

| Node | W × H |
|---|---|
| Pipeline stage | 140 × 80 px |
| Option card | 180 × 220 px |
| Decision diamond | 140 × 80 px |
| Action rectangle | 140 × 50 px |
| Start node | 160 × 50 px |
| Graph node (schema) | 100 × 50 px |
| Participant (seq.) | 140 × 50 px |
| Output box (seed) | 200 × 60 px |

---

## FIGURES AT A GLANCE

| Figure | Type | Key Visual Feature |
|---|---|---|
| 1.1 Pipeline | Horizontal flow | Offline/Online sections, timing badges |
| 1.2 Options | Card comparison | Color-coded badges, bar chart below |
| 1.3 Decision Tree | Top-down flowchart | Diamond nodes, YES/NO color paths |
| 1.4 Code→Graph | 3-column layout | Bezier connectors, syntax highlight |
| 1.5 Property Graph | Node-link diagram | 4 node types, 4 edge styles, legend |
| 1.7 Seed Flow | Funnel diagram | Arrow width = weight, hex merge box |
| 1.8 Sequence | UML sequence | Timing ruler, step circles, data tags |

---

## TABLES AT A GLANCE

| Table | Key Feature |
|---|---|
| 1.1 Complexity | Phase badges, monospace `#DC2626` O-notation |
| 1.2 Entity Types | Icon + color per type, qualified name callout |
| 1.3 Edge Types | Inline line-sample, arrow preview |
| 1.4 IDF Weights | Row banding by weight range (green/yellow/red) |
| 1.5 Recall | Two-row header, Δ column with ± color |
| 1.6 MCP Tools | Primary row highlight, multi-line params |

---

*See `chapter3_visual_redesign_prompt.md` for full specification.*
