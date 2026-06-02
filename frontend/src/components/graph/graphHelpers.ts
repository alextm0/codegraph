import * as d3 from 'd3'
import type { D3Edge, D3Node } from '../../types/graph'

/** Collect node ids plus all direct graph neighbors. */
export function expandWithNeighbors(
  ids: Set<string>,
  edges: D3Edge[],
): Set<string> {
  const out = new Set(ids)
  edges.forEach(e => {
    const sid = typeof e.source === 'object' ? (e.source as D3Node).id : String(e.source)
    const tid = typeof e.target === 'object' ? (e.target as D3Node).id : String(e.target)
    if (out.has(sid)) out.add(tid)
    if (out.has(tid)) out.add(sid)
  })
  return out
}

/** Node ids for all entities belonging to a file. */
export function fileNodeIds(filePath: string, nodes: D3Node[]): Set<string> {
  return new Set(nodes.filter(n => n.file_path === filePath).map(n => n.id))
}

/** In-file entities plus direct neighbors — used for zoom framing only. */
export function fileFocusNodeIds(
  filePath: string,
  nodes: D3Node[],
  edges: D3Edge[],
): Set<string> {
  return expandWithNeighbors(fileNodeIds(filePath, nodes), edges)
}

/** Returns the CSS color for a node label type (reads CSS variables at runtime). */
export function nodeColor(label: string): string {
  const style = getComputedStyle(document.documentElement)
  switch (label) {
    case 'File':     return style.getPropertyValue('--node-file').trim() || 'oklch(0.70 0.12 240)'
    case 'Class':    return style.getPropertyValue('--node-class').trim() || 'oklch(0.74 0.14 145)'
    case 'Function': return style.getPropertyValue('--node-function').trim() || 'oklch(0.80 0.14 75)'
    case 'Method':   return style.getPropertyValue('--node-method').trim() || 'oklch(0.74 0.14 290)'
    default:         return style.getPropertyValue('--text-muted').trim() || 'oklch(0.55 0.010 70)'
  }
}

/** Returns the CSS color for an edge relationship type. */
export function edgeColor(type: string): string {
  const style = getComputedStyle(document.documentElement)
  switch (type) {
    case 'CALLS':         return style.getPropertyValue('--edge-calls').trim() || 'oklch(0.68 0.13 145)'
    case 'IMPORTS':       return style.getPropertyValue('--edge-imports').trim() || 'oklch(0.68 0.12 240)'
    case 'CONTAINS':      return style.getPropertyValue('--edge-contains').trim() || 'oklch(0.45 0.008 60)'
    case 'INHERITS_FROM': return style.getPropertyValue('--edge-inherits').trim() || 'oklch(0.72 0.14 35)'
    default:              return style.getPropertyValue('--text-muted').trim() || 'oklch(0.55 0.010 70)'
  }
}

export function formatScore(score: number): string {
  return score.toFixed(4)
}

export interface FitOptions {
  /** Inner viewport margin in px. */
  padding?: number
  /** Upper bound on zoom-in so sparse graphs are not blown up. */
  maxScale?: number
  /** Lower bound on zoom-out. */
  minScale?: number
  /** Transition duration in ms. */
  duration?: number
}

/** Smoothly fit the viewport to a set of nodes with padding and clamped scale. */
export function fitGraphToView(
  svg: SVGSVGElement,
  nodes: { x?: number; y?: number }[],
  zoom: d3.ZoomBehavior<SVGSVGElement, unknown>,
  width: number,
  height: number,
  opts: FitOptions = {},
): void {
  if (!nodes.length || width <= 0 || height <= 0) return

  const { padding = 56, maxScale = 1.5, minScale = 0.2, duration = 700 } = opts

  const xs = nodes.map(n => n.x ?? 0)
  const ys = nodes.map(n => n.y ?? 0)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const graphW = Math.max(maxX - minX, 1)
  const graphH = Math.max(maxY - minY, 1)

  const rawScale = Math.min(
    (width - padding * 2) / graphW,
    (height - padding * 2) / graphH,
  )
  const scale = Math.max(minScale, Math.min(rawScale, maxScale))
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  const tx = width / 2 - cx * scale
  const ty = height / 2 - cy * scale

  d3.select(svg)
    .transition()
    .duration(duration)
    .ease(d3.easeCubicInOut)
    .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale))
}

/** Apply a multiplicative zoom around the viewport center. */
export function zoomByFactor(
  svg: SVGSVGElement,
  zoom: d3.ZoomBehavior<SVGSVGElement, unknown>,
  factor: number,
  width: number,
  height: number,
): void {
  const current = d3.zoomTransform(svg)
  const nextK = Math.min(6, Math.max(0.25, current.k * factor))
  const cx = width / 2
  const cy = height / 2
  const tx = cx - (cx - current.x) * (nextK / current.k)
  const ty = cy - (cy - current.y) * (nextK / current.k)
  d3.select(svg)
    .transition()
    .duration(280)
    .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(nextK))
}
