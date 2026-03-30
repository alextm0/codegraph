import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { D3Node, D3Edge } from '../../types/graph'
import type { GraphNode } from '../../types/api'
import { edgeColor } from './graphHelpers'

interface GraphCanvasProps {
  nodes: D3Node[]
  edges: D3Edge[]
  onNodeSelect: (node: GraphNode) => void
}

const EDGE_TYPES = ['CALLS', 'IMPORTS', 'CONTAINS', 'INHERITS_FROM'] as const

// Tooltip singleton
let _tooltip: HTMLDivElement | null = null
function getTooltip(): HTMLDivElement {
  if (!_tooltip) {
    _tooltip = document.createElement('div')
    _tooltip.style.cssText = [
      'position:fixed', 'background:var(--surface2)', 'border:1px solid var(--border)',
      'border-radius:var(--radius-md)', 'padding:8px 10px', 'pointer-events:none',
      'z-index:999', 'max-width:260px', 'box-shadow:var(--shadow)',
      'font-size:11px', 'display:none',
    ].join(';')
    document.body.appendChild(_tooltip)
  }
  return _tooltip
}

function showTooltip(e: MouseEvent, d: D3Node) {
  const tt = getTooltip()
  const sc = d.ppr_score > 0 ? d.ppr_score.toFixed(4) : '—'
  const seedPart = d.is_seed ? ` · seed ${d.seed_weight.toFixed(3)}` : ''
  tt.innerHTML =
    `<div style="font-family:var(--mono);font-weight:600;color:var(--text);margin-bottom:2px;word-break:break-all">${d.name}</div>` +
    `<div style="font-family:var(--mono);color:var(--text-dim);font-size:10px;margin-bottom:4px;word-break:break-all">${d.file_path ?? ''}</div>` +
    `<div style="font-variant-numeric:tabular-nums slashed-zero;font-family:var(--mono);font-size:10px">PPR: ${sc}${seedPart}</div>`
  tt.style.display = 'block'
  tt.style.left = `${e.clientX + 14}px`
  tt.style.top = `${e.clientY - 28}px`
}

function moveTooltip(e: MouseEvent) {
  const tt = getTooltip()
  tt.style.left = `${e.clientX + 14}px`
  tt.style.top = `${e.clientY - 28}px`
}

function hideTooltip() {
  getTooltip().style.display = 'none'
}

function nodeRadius(d: D3Node): number {
  if (d.is_seed) return 11
  return Math.max(5, 4 + d.ppr_score * 28)
}

function nodeVisualColor(d: D3Node): string {
  if (d.is_seed) return '#d4af37'
  if (d.ppr_score <= 0) return '#2d3748'
  // Heat map: blue (low) → red (high) based on PPR score
  return d3.interpolateRdYlBu(1 - Math.min(d.ppr_score / 0.4, 1))
}

export default function GraphCanvas({ nodes, edges, onNodeSelect }: GraphCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const simRef = useRef<d3.Simulation<D3Node, D3Edge> | null>(null)
  const sizeRef = useRef({ w: 800, h: 600 })

  // ResizeObserver to track container size
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const parent = svg.parentElement
    if (!parent) return

    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      sizeRef.current = { w: Math.floor(width), h: Math.floor(height) }
    })
    ro.observe(parent)
    return () => ro.disconnect()
  }, [])

  // D3 simulation
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return

    // Cleanup previous simulation
    d3.select(svg).selectAll('*').remove()
    if (simRef.current) {
      simRef.current.stop()
      simRef.current = null
    }
    if (!nodes.length) return

    const parent = svg.parentElement
    const rect = parent?.getBoundingClientRect()
    const W = sizeRef.current.w || rect?.width || 800
    const H = sizeRef.current.h || rect?.height || 600

    const svgSel = d3.select(svg)

    // Arrow markers for each edge type
    const defs = svgSel.append('defs')
    EDGE_TYPES.forEach((rel) => {
      const color = edgeColor(rel)
      defs
        .append('marker')
        .attr('id', `arr-${rel}`)
        .attr('viewBox', '0 -4 8 8')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 5)
        .attr('markerHeight', 5)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', color)
    })

    const g = svgSel.append('g')

    // Zoom + pan
    svgSel.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.15, 5])
        .on('zoom', (e) => g.attr('transform', e.transform)),
    )

    // Build id→node map for resolving edge references
    const nodeById: Record<string, D3Node> = {}
    nodes.forEach((n) => { nodeById[n.id] = n })

    // Resolve edges so source/target are node objects
    const links: D3Edge[] = edges
      .map((e) => ({
        source: nodeById[e.source as string] ?? e.source,
        target: nodeById[e.target as string] ?? e.target,
        type: e.type,
      }))
      .filter(
        (e) => e.source && e.target &&
          typeof e.source === 'object' &&
          typeof e.target === 'object',
      )

    // Edge lines
    const linkSel = g
      .append('g')
      .attr('stroke-opacity', 0.55)
      .selectAll<SVGLineElement, D3Edge>('line')
      .data(links)
      .join('line')
      .attr('stroke', (d) => edgeColor(d.type))
      .attr('stroke-width', 1.5)
      .attr('marker-end', (d) => `url(#arr-${d.type})`)

    // Invisible hit area (larger click target)
    const hitSel = g
      .append('g')
      .selectAll<SVGCircleElement, D3Node>('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (d) => nodeRadius(d) + 9)
      .attr('fill', 'transparent')
      .attr('cursor', 'pointer')
      .on('click', (_e, d) => { onNodeSelect(d) })
      .on('mouseover', (_e, d) => showTooltip(_e as unknown as MouseEvent, d))
      .on('mousemove', (e) => moveTooltip(e as unknown as MouseEvent))
      .on('mouseout', hideTooltip)

    // Visible node circles
    const nodeSel = g
      .append('g')
      .selectAll<SVGCircleElement, D3Node>('circle')
      .data(nodes)
      .join('circle')
      .attr('r', nodeRadius)
      .attr('fill', nodeVisualColor)
      .attr('stroke', (d) => d.is_seed ? '#d4af37' : 'rgba(255,255,255,0.12)')
      .attr('stroke-width', (d) => d.is_seed ? 2.5 : 1)
      .attr('cursor', 'pointer')
      .on('click', (_e, d) => { onNodeSelect(d) })
      .on('mouseover', (_e, d) => showTooltip(_e as unknown as MouseEvent, d))
      .on('mousemove', (e) => moveTooltip(e as unknown as MouseEvent))
      .on('mouseout', hideTooltip)

    // Labels for seeds and top-PPR nodes only
    const topIds = new Set([
      ...nodes.filter((d) => d.is_seed).map((d) => d.id),
      ...[...nodes]
        .sort((a, b) => b.ppr_score - a.ppr_score)
        .slice(0, 6)
        .map((d) => d.id),
    ])

    const labelSel = g
      .append('g')
      .selectAll<SVGTextElement, D3Node>('text')
      .data(nodes.filter((d) => topIds.has(d.id)))
      .join('text')
      .text((d) => (d.name.length > 22 ? `${d.name.slice(0, 20)}…` : d.name))
      .attr('font-size', 9)
      .attr('fill', '#94a3b8')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => nodeRadius(d) + 11)
      .attr('pointer-events', 'none')

    // Drag behaviour
    nodeSel.call(
      d3.drag<SVGCircleElement, D3Node>()
        .on('start', (e, d) => {
          if (!e.active) sim.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (e, d) => {
          d.fx = e.x
          d.fy = e.y
        })
        .on('end', (e, d) => {
          if (!e.active) sim.alphaTarget(0)
          d.fx = null
          d.fy = null
        }),
    )

    // Force simulation
    const sim = d3
      .forceSimulation<D3Node, D3Edge>(nodes)
      .force('link', d3.forceLink<D3Node, D3Edge>(links).id((d) => d.id).distance(100).strength(0.35))
      .force('charge', d3.forceManyBody<D3Node>().strength(-250))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide<D3Node>().radius((d) => nodeRadius(d) + 12))
      .on('tick', () => {
        linkSel
          .attr('x1', (d) => (d.source as D3Node).x ?? 0)
          .attr('y1', (d) => (d.source as D3Node).y ?? 0)
          .attr('x2', (d) => (d.target as D3Node).x ?? 0)
          .attr('y2', (d) => (d.target as D3Node).y ?? 0)
        nodeSel.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0)
        hitSel.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0)
        labelSel.attr('x', (d) => d.x ?? 0).attr('y', (d) => d.y ?? 0)
      })

    simRef.current = sim

    return () => {
      sim.stop()
      hideTooltip()
    }
  }, [nodes, edges, onNodeSelect])

  const hasData = nodes.length > 0

  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minWidth: 0, height: '100%' }}>
      {!hasData && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            gap: 16,
            color: 'var(--text-dim)',
          }}
        >
          <div style={{ fontSize: 40, opacity: 0.2 }}>⬡</div>
          <div style={{ fontSize: 13 }}>Enter a task description and click Run</div>
        </div>
      )}
      <svg
        ref={svgRef}
        style={{ width: '100%', height: '100%', display: hasData ? 'block' : 'none' }}
      />
      {hasData && <GraphLegend />}
    </div>
  )
}

function GraphLegend() {
  const nodeTypes: [string, string][] = [
    ['#d4af37', 'Seed'],
    ['#f87171', 'High PPR'],
    ['#60a5fa', 'Low PPR'],
    ['#2d3748', 'Graph entity'],
  ]
  const edgeTypes: [string, string][] = [
    [edgeColor('CALLS'), 'CALLS'],
    [edgeColor('IMPORTS'), 'IMPORTS'],
    [edgeColor('CONTAINS'), 'CONTAINS'],
    [edgeColor('INHERITS_FROM'), 'INHERITS_FROM'],
  ]

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 12,
        left: 12,
        background: 'rgba(15,17,23,0.9)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: '10px 14px',
        fontSize: 10,
        backdropFilter: 'blur(8px)',
        pointerEvents: 'none',
      }}
    >
      <div style={{ color: 'var(--text-dim)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Nodes
      </div>
      {nodeTypes.map(([c, l]) => (
        <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2, color: 'var(--text-dim)' }}>
          <div style={{ width: 9, height: 9, borderRadius: '50%', background: c, flexShrink: 0 }} />
          {l}
        </div>
      ))}
      <div style={{ color: 'var(--text-dim)', fontWeight: 600, marginTop: 8, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Edges
      </div>
      {edgeTypes.map(([c, l]) => (
        <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2, color: 'var(--text-dim)' }}>
          <div style={{ width: 20, height: 2, background: c, flexShrink: 0 }} />
          {l}
        </div>
      ))}
    </div>
  )
}
