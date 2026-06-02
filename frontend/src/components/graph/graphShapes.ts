import * as d3 from 'd3'
import type { D3Node, D3Edge } from '../../types/graph'
import { nodeColor } from './graphHelpers'

/** Radius used for force layout collision and sizing. */
export function nodeRadius(d: D3Node): number {
  const base = d.is_seed ? 11 : 6
  return base + Math.sqrt(Math.max(0, d.ppr_score || 0)) * 28
}

/** Straight path between two positioned nodes. */
export function linkPath(d: D3Edge): string {
  const sx = (d.source as D3Node).x ?? 0
  const sy = (d.source as D3Node).y ?? 0
  const tx = (d.target as D3Node).x ?? 0
  const ty = (d.target as D3Node).y ?? 0
  return `M${sx},${sy} L${tx},${ty}`
}

/** Point along the straight link at parameter t in [0,1]. */
export function linkPointAt(d: D3Edge, t: number): { x: number; y: number } {
  const sx = (d.source as D3Node).x ?? 0
  const sy = (d.source as D3Node).y ?? 0
  const tx = (d.target as D3Node).x ?? 0
  const ty = (d.target as D3Node).y ?? 0
  return {
    x: sx + (tx - sx) * t,
    y: sy + (ty - sy) * t,
  }
}

/** Stable phase offset per edge for desynchronized animation. */
export function linkPhase(d: D3Edge): number {
  const sid = typeof d.source === 'object' ? (d.source as D3Node).id : String(d.source)
  const tid = typeof d.target === 'object' ? (d.target as D3Node).id : String(d.target)
  let h = 0
  for (const c of sid + tid) h = (h * 31 + c.charCodeAt(0)) % 997
  return h / 997
}

/** Draw entity shape into a D3 selection group centered at 0,0. */
export function appendNodeShape(
  group: d3.Selection<SVGGElement, D3Node, SVGGElement, unknown>,
): void {
  group.each(function (d) {
    const g = d3.select(this)
    const r = nodeRadius(d)
    const fill = nodeColor(d.label)
    g.selectAll('*').remove()

    if (d.label === 'File') {
      g.append('rect')
        .attr('x', -r * 0.9)
        .attr('y', -r * 0.65)
        .attr('width', r * 1.8)
        .attr('height', r * 1.3)
        .attr('rx', 2)
        .attr('fill', fill)
        .attr('stroke', 'var(--bg)')
        .attr('stroke-width', 1.5)
    } else if (d.label === 'Class') {
      g.append('polygon')
        .attr('points', `0,${-r} ${r},0 0,${r} ${-r},0`)
        .attr('fill', fill)
        .attr('stroke', 'var(--bg)')
        .attr('stroke-width', 1.5)
    } else if (d.label === 'Method') {
      const pts = Array.from({ length: 6 }, (_, i) => {
        const a = (Math.PI / 3) * i - Math.PI / 6
        return `${Math.cos(a) * r},${Math.sin(a) * r}`
      }).join(' ')
      g.append('polygon').attr('points', pts).attr('fill', fill).attr('stroke', 'var(--bg)').attr('stroke-width', 1.5)
    } else {
      g.append('circle')
        .attr('r', r)
        .attr('fill', fill)
        .attr('stroke', 'var(--bg)')
        .attr('stroke-width', 1.5)
    }

    if ((d.ppr_score || 0) > 0.05 || d.is_seed) {
      g.attr('filter', 'url(#glow)')
    }
  })
}
