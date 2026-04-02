import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { D3Node, D3Edge } from '../../types/graph'
import type { GraphNode } from '../../types/api'
import { nodeColor, edgeColor } from './graphHelpers'

interface GraphCanvasProps {
  nodes: D3Node[]
  edges: D3Edge[]
  onNodeSelect: (node: GraphNode | null) => void
  selectedNode?: GraphNode | null
}

const EDGE_TYPES = ['CALLS', 'IMPORTS', 'CONTAINS', 'INHERITS_FROM'] as const

function createTooltipEl(): HTMLDivElement {
  const el = document.createElement('div')
  el.style.cssText = [
    'position:fixed', 'background:var(--surface2)', 'border:1px solid var(--border)',
    'border-radius:var(--radius-md)', 'padding:8px 10px', 'pointer-events:none',
    'z-index:999', 'max-width:260px', 'box-shadow:var(--shadow)',
    'font-size:11px', 'display:none',
  ].join(';')
  document.body.appendChild(el)
  return el
}

function showTooltip(tt: HTMLDivElement, e: MouseEvent, d: D3Node) {
  const ppr = d.ppr_score || 0
  const sc = ppr > 0 ? ppr.toFixed(5) : '—'
  const seedPart = d.is_seed ? ` · seed ${(d.seed_weight || 0).toFixed(3)}` : ''

  tt.innerHTML = ''

  const nameEl = document.createElement('div')
  nameEl.style.cssText = 'font-family:var(--mono);font-weight:600;color:var(--text);margin-bottom:2px;word-break:break-all'
  nameEl.textContent = d.name
  tt.appendChild(nameEl)

  const pathEl = document.createElement('div')
  pathEl.style.cssText = 'font-family:var(--mono);color:var(--text-dim);font-size:10px;margin-bottom:4px;word-break:break-all'
  pathEl.textContent = d.file_path ?? ''
  tt.appendChild(pathEl)

  const scoreEl = document.createElement('div')
  scoreEl.style.cssText = 'font-variant-numeric:tabular-nums slashed-zero;font-family:var(--mono);font-size:10px'
  scoreEl.textContent = `PPR: ${sc}${seedPart}`
  tt.appendChild(scoreEl)

  tt.style.display = 'block'
  tt.style.left = `${e.clientX + 14}px`
  tt.style.top = `${e.clientY - 28}px`
}

function moveTooltip(tt: HTMLDivElement, e: MouseEvent) {
  tt.style.left = `${e.clientX + 14}px`
  tt.style.top = `${e.clientY - 28}px`
}

function hideTooltip(tt: HTMLDivElement) {
  tt.style.display = 'none'
}

function nodeRadius(d: D3Node): number {
  const base = d.is_seed ? 10 : 6
  const ppr = d.ppr_score || 0
  return base + Math.sqrt(Math.max(0, ppr)) * 25
}

export default function GraphCanvas({ nodes, edges, onNodeSelect, selectedNode }: GraphCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const simRef = useRef<d3.Simulation<D3Node, D3Edge> | null>(null)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const sizeRef = useRef({ w: 800, h: 600 })
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const requestRef = useRef<number>()

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

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return

    const tt = createTooltipEl()
    tooltipRef.current = tt

    d3.select(svg).selectAll('*').remove()
    if (simRef.current) {
      simRef.current.stop()
      simRef.current = null
    }
    if (!nodes.length) {
      return () => {
        tt.remove()
        tooltipRef.current = null
      }
    }

    const parent = svg.parentElement
    const rect = parent?.getBoundingClientRect()
    const W = sizeRef.current.w || rect?.width || 800
    const H = sizeRef.current.h || rect?.height || 600

    const svgSel = d3.select(svg)

    const defs = svgSel.append('defs')

    // Glow filter
    const filter = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-50%')
      .attr('y', '-50%')
      .attr('width', '200%')
      .attr('height', '200%')

    filter.append('feGaussianBlur')
      .attr('stdDeviation', '2.5')
      .attr('result', 'coloredBlur')

    const feMerge = filter.append('feMerge')
    feMerge.append('feMergeNode').attr('in', 'coloredBlur')
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    // Arrow markers
    EDGE_TYPES.forEach((rel) => {
      const color = edgeColor(rel)
      
      // Standard marker
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

      // Dimmed marker
      defs
        .append('marker')
        .attr('id', `arr-${rel}-dim`)
        .attr('viewBox', '0 -4 8 8')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 5)
        .attr('markerHeight', 5)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', color)
        .attr('fill-opacity', 0.1)
    })

    const g = svgSel.append('g')

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 8])
      .on('zoom', (e) => g.attr('transform', e.transform))
      
    svgSel.call(zoom)
    zoomRef.current = zoom

    const nodeById: Record<string, D3Node> = {}
    nodes.forEach((n) => { nodeById[n.id] = n })

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

    const linkSel = g
      .append('g')
      .attr('stroke-opacity', 0.4)
      .selectAll<SVGLineElement, D3Edge>('line')
      .data(links)
      .join('line')
      .attr('stroke', (d) => edgeColor(d.type))
      .attr('stroke-width', 1.2)
      .attr('marker-end', (d) => `url(#arr-${d.type})`)

    // Particle animation layer
    const particleGroup = g.append('g')
    const animatedLinks = links.filter(l => l.type === 'CALLS' || l.type === 'IMPORTS')
    const particles = particleGroup
      .selectAll<SVGCircleElement, D3Edge>('circle.particle')
      .data(animatedLinks)
      .join('circle')
      .attr('class', 'particle')
      .attr('r', 2)
      .attr('fill', d => edgeColor(d.type))
      .attr('opacity', 0.8)

    const startTime = Date.now()
    const animate = () => {
      const elapsed = (Date.now() - startTime) % 2000
      const t = elapsed / 2000

      particles
        .attr('cx', d => {
          const x1 = (d.source as D3Node).x || 0
          const x2 = (d.target as D3Node).x || 0
          return x1 + (x2 - x1) * t
        })
        .attr('cy', d => {
          const y1 = (d.source as D3Node).y || 0
          const y2 = (d.target as D3Node).y || 0
          return y1 + (y2 - y1) * t
        })

      requestRef.current = requestAnimationFrame(animate)
    }
    requestRef.current = requestAnimationFrame(animate)

    const nodeGroup = g.append('g')

    // Seed node animated ring
    const seedRings = nodeGroup
      .selectAll<SVGCircleElement, D3Node>('circle.seed-ring')
      .data(nodes.filter(d => d.is_seed))
      .join('circle')
      .attr('class', 'seed-ring')
      .attr('r', d => nodeRadius(d) + 4)
      .attr('fill', 'none')
      .attr('stroke', '#fbbf24')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.6)
    
    seedRings.append('animate')
      .attr('attributeName', 'stroke-opacity')
      .attr('values', '0.6;0.1;0.6')
      .attr('dur', '2s')
      .attr('repeatCount', 'indefinite')

    // Visible node circles
    const nodeSel = nodeGroup
      .selectAll<SVGCircleElement, D3Node>('circle.node')
      .data(nodes)
      .join('circle')
      .attr('class', 'node')
      .attr('r', nodeRadius)
      .attr('fill', (d) => nodeColor(d.label))
      .attr('filter', (d) => (d.ppr_score || 0) > 0.05 ? 'url(#glow)' : null)
      .attr('stroke', 'rgba(255,255,255,0.2)')
      .attr('stroke-width', 1)
      .attr('cursor', 'pointer')
      .on('click', (_e, d) => { onNodeSelect(d) })
      .on('mouseover', (_e, d) => showTooltip(tt, _e as unknown as MouseEvent, d))
      .on('mousemove', (e) => moveTooltip(tt, e as unknown as MouseEvent))
      .on('mouseout', () => hideTooltip(tt))

    const labelSel = g
      .append('g')
      .selectAll<SVGTextElement, D3Node>('text')
      .data(nodes)
      .join('text')
      .text(d => d.name || d.file_path || "Unknown")
      .attr('font-size', d => d.is_seed || (d.ppr_score || 0) > 0.05 ? 10 : 9)
      .attr('fill', 'var(--text)')
      .attr('opacity', d => d.is_seed || (d.ppr_score || 0) > 0.05 ? 1 : 0.5)
      .attr('text-anchor', 'middle')
      .attr('dy', d => nodeRadius(d) + 14)
      .attr('pointer-events', 'none')
      .style('text-shadow', '0 1px 2px rgba(0,0,0,0.8)')

    const sim = d3
      .forceSimulation<D3Node, D3Edge>(nodes)
      .force('link', d3.forceLink<D3Node, D3Edge>(links).id((d) => d.id).distance(120).strength(0.2))
      .force('charge', d3.forceManyBody<D3Node>().strength(-200))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide<D3Node>().radius((d) => nodeRadius(d) + 10))
      .on('tick', () => {
        linkSel
          .attr('x1', (d) => (d.source as D3Node).x ?? 0)
          .attr('y1', (d) => (d.source as D3Node).y ?? 0)
          .attr('x2', (d) => (d.target as D3Node).x ?? 0)
          .attr('y2', (d) => (d.target as D3Node).y ?? 0)
        nodeSel.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0)
        seedRings.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0)
        labelSel.attr('x', (d) => d.x ?? 0).attr('y', (d) => d.y ?? 0)
      })

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

    simRef.current = sim

    return () => {
      sim.stop()
      if (requestRef.current) cancelAnimationFrame(requestRef.current)
      hideTooltip(tt)
      tt.remove()
      tooltipRef.current = null
    }
  }, [nodes, edges, onNodeSelect])

  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    const nodeSel = svg.selectAll<SVGCircleElement, D3Node>('circle.node')
    const linkSel = svg.selectAll<SVGLineElement, D3Edge>('line')
    const labelSel = svg.selectAll<SVGTextElement, D3Node>('text')
    const ringSel = svg.selectAll<SVGCircleElement, D3Node>('circle.seed-ring')
    const particleSel = svg.selectAll<SVGCircleElement, D3Edge>('circle.particle')

    if (!selectedNode) {
      // Restore standard opacities
      nodeSel.attr('opacity', 1)
      ringSel.attr('opacity', 1)
      linkSel.attr('stroke-opacity', 0.4).attr('marker-end', d => `url(#arr-${d.type})`)
      labelSel.attr('opacity', d => d.is_seed || (d.ppr_score || 0) > 0.05 ? 1 : 0.5)
      particleSel.attr('opacity', 0.8)
      return
    }

    const connected = new Set<string>([selectedNode.id])
    edges.forEach(e => {
        const sourceId = typeof e.source === 'object' ? (e.source as D3Node).id : e.source
        const targetId = typeof e.target === 'object' ? (e.target as D3Node).id : e.target
        if (sourceId === selectedNode.id) connected.add(targetId as string)
        if (targetId === selectedNode.id) connected.add(sourceId as string)
    })

    nodeSel.attr('opacity', d => connected.has(d.id) ? 1 : 0.05)
    ringSel.attr('opacity', d => connected.has(d.id) ? 1 : 0)
    linkSel
      .attr('stroke-opacity', d => {
        const sourceId = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
        const targetId = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
        return (sourceId === selectedNode.id || targetId === selectedNode.id) ? 0.8 : 0.05
      })
      .attr('marker-end', d => {
        const sourceId = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
        const targetId = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
        const isConnected = sourceId === selectedNode.id || targetId === selectedNode.id
        return isConnected ? `url(#arr-${d.type})` : `url(#arr-${d.type}-dim)`
      })

    labelSel.attr('opacity', d => connected.has(d.id) ? 1 : 0.05)
    
    particleSel.attr('opacity', d => {
      const sourceId = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
      const targetId = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
      return (sourceId === selectedNode.id || targetId === selectedNode.id) ? 0.8 : 0.01
    })

    const sn = nodes.find(n => n.id === selectedNode.id)
    if (sn && sn.x !== undefined && sn.y !== undefined && zoomRef.current) {
      const W = sizeRef.current.w
      const H = sizeRef.current.h
      const scale = 2
      const tx = W / 2 - sn.x * scale
      const ty = H / 2 - sn.y * scale

      svg.transition()
        .duration(750)
        .call(zoomRef.current.transform, d3.zoomIdentity.translate(tx, ty).scale(scale))
    }
  }, [selectedNode, nodes, edges])

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
    [nodeColor('File'), 'File'],
    [nodeColor('Class'), 'Class'],
    [nodeColor('Function'), 'Function'],
    [nodeColor('Method'), 'Method'],
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
        display: 'flex',
        gap: 20
      }}
    >
      <div>
        <div style={{ color: 'var(--text-dim)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Nodes
        </div>
        {nodeTypes.map(([c, l]) => (
          <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2, color: 'var(--text-dim)' }}>
            <div style={{ width: 9, height: 9, borderRadius: '50%', background: c, flexShrink: 0 }} />
            {l}
          </div>
        ))}
      </div>
      <div>
        <div style={{ color: 'var(--text-dim)', fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Edges
        </div>
        {edgeTypes.map(([c, l]) => (
          <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2, color: 'var(--text-dim)' }}>
            <div style={{ width: 20, height: 2, background: c, flexShrink: 0 }} />
            {l}
          </div>
        ))}
      </div>
    </div>
  )
}
