import type { D3Edge, D3Node } from '../../types/graph'
import type { GraphColors } from './graphHelpers'
import { edgeColorFrom } from './graphHelpers'
import { nodeRadius, linkPhase } from './graphShapes'

/** Highlight state shared between the SVG node layer and the canvas edge layer. */
export interface HighlightState {
  isPathActive: boolean
  pathNodeIds: Set<string>
  highlightIds: Set<string>
}

interface SceneOptions {
  links: D3Edge[]
  particleLinks: D3Edge[]
  transform: { k: number; x: number; y: number }
  colors: GraphColors
  dpr: number
  width: number
  height: number
  highlight: HighlightState | null
  showParticles: boolean
  showArrows: boolean
  elapsed: number
  /** Query/focus subgraphs rely on CONTAINS edges from File nodes. */
  emphasizeStructural?: boolean
}

interface EdgeStyle {
  color: string
  width: number
  opacity: number
  dashed: boolean
  arrowColor: string
  arrowOpacity: number
}

const DASHED_TYPES = new Set(['CONTAINS', 'INHERITS_FROM'])
const PARTICLE_TYPES = new Set(['CALLS', 'IMPORTS'])
/* Structural scaffolding edges sit visually behind the semantic ones. */
const STRUCTURAL_TYPES = new Set(['CONTAINS'])

/** Gentle perpendicular bow so overlapping edges separate (reduces hairball). */
function controlPoint(
  sx: number, sy: number, tx: number, ty: number,
): { cx: number; cy: number } {
  const dx = tx - sx, dy = ty - sy
  const len = Math.hypot(dx, dy) || 1
  const bow = Math.min(len * 0.12, 34)
  return { cx: (sx + tx) / 2 - (dy / len) * bow, cy: (sy + ty) / 2 + (dx / len) * bow }
}

/** Point on the quadratic curve at parameter t in [0,1]. */
function quadPointAt(
  sx: number, sy: number, cx: number, cy: number, tx: number, ty: number, t: number,
): { x: number; y: number } {
  const u = 1 - t
  return {
    x: u * u * sx + 2 * u * t * cx + t * t * tx,
    y: u * u * sy + 2 * u * t * cy + t * t * ty,
  }
}

/** Multiplier that thins the edge field when zoomed out (de-hairballs). */
function zoomEdgeAlpha(k: number): number {
  if (k >= 1) return 1
  if (k <= 0.35) return 0.5
  return 0.5 + ((k - 0.35) / 0.65) * 0.5
}

/** Size a canvas backing store for the device pixel ratio. */
export function sizeCanvas(
  canvas: HTMLCanvasElement,
  width: number,
  height: number,
  dpr: number,
): void {
  canvas.width = Math.max(1, Math.floor(width * dpr))
  canvas.height = Math.max(1, Math.floor(height * dpr))
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
}

function endpointId(end: string | D3Node): string {
  return typeof end === 'object' ? (end as D3Node).id : String(end)
}

/** Resolve the per-edge stroke/arrow style given the active highlight state. */
function edgeStyle(
  edge: D3Edge,
  colors: GraphColors,
  highlight: HighlightState | null,
  emphasizeStructural: boolean,
): EdgeStyle {
  const base = edgeColorFrom(colors, edge.type)
  const dashed = DASHED_TYPES.has(edge.type)
  const structural = STRUCTURAL_TYPES.has(edge.type)
  const baseWidth = structural ? (emphasizeStructural ? 1.1 : 0.8) : 1
  const baseOpacity = structural
    ? (emphasizeStructural ? 0.48 : 0.14)
    : 0.26

  if (!highlight) {
    return {
      color: base, width: baseWidth, opacity: baseOpacity, dashed,
      arrowColor: base, arrowOpacity: structural ? (emphasizeStructural ? 0.65 : 0.3) : 0.5,
    }
  }

  const sid = endpointId(edge.source)
  const tid = endpointId(edge.target)

  if (highlight.isPathActive) {
    const onPath = highlight.pathNodeIds.has(sid) && highlight.pathNodeIds.has(tid)
    return onPath
      ? { color: colors.accent, width: 3.5, opacity: 1, dashed: false, arrowColor: colors.accent, arrowOpacity: 1 }
      : { color: base, width: 1, opacity: 0.035, dashed, arrowColor: base, arrowOpacity: 0.035 }
  }

  const lit = highlight.highlightIds.has(sid) && highlight.highlightIds.has(tid)
  return lit
    ? { color: base, width: 2, opacity: 1, dashed, arrowColor: base, arrowOpacity: 0.9 }
    : { color: base, width: 1, opacity: 0.03, dashed, arrowColor: base, arrowOpacity: 0.03 }
}

function styleKey(s: EdgeStyle): string {
  return `${s.color}|${s.width}|${s.opacity}|${s.dashed ? 1 : 0}|${s.arrowColor}|${s.arrowOpacity}`
}

/** Group edges by identical resolved style so each batch is one stroke pass. */
function bucketEdges(
  links: D3Edge[],
  colors: GraphColors,
  highlight: HighlightState | null,
  emphasizeStructural: boolean,
): Map<string, { style: EdgeStyle; edges: D3Edge[] }> {
  const buckets = new Map<string, { style: EdgeStyle; edges: D3Edge[] }>()
  for (const edge of links) {
    const style = edgeStyle(edge, colors, highlight, emphasizeStructural)
    const key = styleKey(style)
    const bucket = buckets.get(key)
    if (bucket) bucket.edges.push(edge)
    else buckets.set(key, { style, edges: [edge] })
  }
  return buckets
}

function drawArrow(
  ctx: CanvasRenderingContext2D,
  edge: D3Edge,
  size: number,
): void {
  const s = edge.source as D3Node
  const t = edge.target as D3Node
  const sx = s.x ?? 0, sy = s.y ?? 0
  const tx = t.x ?? 0, ty = t.y ?? 0
  const { cx, cy } = controlPoint(sx, sy, tx, ty)
  // Tangent at the curve's end points from the control handle to the target.
  const dx = tx - cx, dy = ty - cy
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len, uy = dy / len
  const r = nodeRadius(t)
  const tipX = tx - ux * (r + 1.5)
  const tipY = ty - uy * (r + 1.5)
  const px = -uy, py = ux
  ctx.moveTo(tipX, tipY)
  ctx.lineTo(tipX - ux * size + px * size * 0.6, tipY - uy * size + py * size * 0.6)
  ctx.lineTo(tipX - ux * size - px * size * 0.6, tipY - uy * size - py * size * 0.6)
  ctx.closePath()
}

/** Stroke every edge bucket as gentle curves, then optional arrowheads. */
function drawEdges(
  ctx: CanvasRenderingContext2D,
  opts: SceneOptions,
): void {
  const { k } = opts.transform
  const emphasizeStructural = opts.emphasizeStructural ?? false
  const buckets = bucketEdges(
    opts.links,
    opts.colors,
    opts.highlight,
    emphasizeStructural,
  )
  const arrowSize = 6 / k
  const fade = opts.highlight ? 1 : zoomEdgeAlpha(k)

  for (const { style, edges } of buckets.values()) {
    ctx.globalAlpha = style.opacity * fade
    ctx.strokeStyle = style.color
    ctx.lineWidth = style.width / k
    ctx.setLineDash(style.dashed ? [4 / k, 4 / k] : [])
    ctx.beginPath()
    for (const edge of edges) {
      const s = edge.source as D3Node
      const t = edge.target as D3Node
      const sx = s.x ?? 0, sy = s.y ?? 0
      const tx = t.x ?? 0, ty = t.y ?? 0
      const { cx, cy } = controlPoint(sx, sy, tx, ty)
      ctx.moveTo(sx, sy)
      ctx.quadraticCurveTo(cx, cy, tx, ty)
    }
    ctx.stroke()

    if (opts.showArrows && style.arrowOpacity > 0.15) {
      ctx.setLineDash([])
      ctx.globalAlpha = style.arrowOpacity * fade
      ctx.fillStyle = style.arrowColor
      ctx.beginPath()
      for (const edge of edges) drawArrow(ctx, edge, arrowSize)
      ctx.fill()
    }
  }
  ctx.setLineDash([])
}

/** Paint travelling particles along CALLS / IMPORTS edges. */
function drawParticles(
  ctx: CanvasRenderingContext2D,
  opts: SceneOptions,
): void {
  const { k } = opts.transform
  const radius = 1.8 / k
  const highlight = opts.highlight

  for (const edge of opts.particleLinks) {
    if (!PARTICLE_TYPES.has(edge.type)) continue
    const s = edge.source as D3Node
    const t = edge.target as D3Node
    const period = edge.type === 'CALLS' ? 1800 : 2200
    const phase = linkPhase(edge)
    const f = ((opts.elapsed % period) / period + phase) % 1

    let opacity = 0.85
    let r = radius
    if (highlight) {
      const sid = endpointId(edge.source)
      const tid = endpointId(edge.target)
      const lit = highlight.isPathActive
        ? highlight.pathNodeIds.has(sid) && highlight.pathNodeIds.has(tid)
        : highlight.highlightIds.has(sid) && highlight.highlightIds.has(tid)
      opacity = lit ? 1 : highlight.isPathActive ? 0.05 : 0.04
      r = lit ? (highlight.isPathActive ? 3.5 : 3) / k : radius
    }

    const sx = s.x ?? 0, sy = s.y ?? 0
    const tx = t.x ?? 0, ty = t.y ?? 0
    const { cx, cy } = controlPoint(sx, sy, tx, ty)
    const p = quadPointAt(sx, sy, cx, cy, tx, ty, f)

    ctx.globalAlpha = opacity
    ctx.fillStyle = edgeColorFrom(opts.colors, edge.type)
    ctx.beginPath()
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2)
    ctx.fill()
  }
}

/** Clear and redraw the full edge + particle scene under the shared transform. */
export function drawScene(
  ctx: CanvasRenderingContext2D,
  opts: SceneOptions,
): void {
  const { dpr, width, height, transform } = opts
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)
  ctx.translate(transform.x, transform.y)
  ctx.scale(transform.k, transform.k)
  ctx.lineCap = 'round'

  drawEdges(ctx, opts)
  if (opts.showParticles) drawParticles(ctx, opts)
  ctx.globalAlpha = 1
}
