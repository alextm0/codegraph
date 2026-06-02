import { useEffect, useRef, useState, useMemo } from 'react'
import * as d3 from 'd3'
import type { D3Node, D3Edge } from '../../types/graph'
import type { GraphNode } from '../../types/api'
import { nodeColor, edgeColor } from './graphHelpers'

import { initializeProject, ProjectHistoryItem } from '../../api/client'

interface GraphCanvasProps {
  nodes: D3Node[]
  edges: D3Edge[]
  onNodeSelect: (node: GraphNode | null) => void
  selectedNode?: GraphNode | null
  dampingFactor?: number
  topK?: number
  projectHistory?: ProjectHistoryItem[]
  isDatabaseEmpty?: boolean
}

const EDGE_TYPES = ['CALLS', 'IMPORTS', 'CONTAINS', 'INHERITS_FROM'] as const

function nodeRadius(d: D3Node): number {
  const base = d.is_seed ? 11 : 6
  return base + Math.sqrt(Math.max(0, d.ppr_score || 0)) * 28
}

/* ── Tooltip ──────────────────────────────────────────────── */
function createTooltipEl(): HTMLDivElement {
  const el = document.createElement('div')
  el.style.cssText = [
    'position:fixed',
    'background:var(--surface2)',
    'border:1px solid var(--border)',
    'padding:8px 12px',
    'pointer-events:none',
    'z-index:999',
    'max-width:280px',
    'font-size:10px',
    'font-family:var(--font-mono)',
    'display:none',
    'letter-spacing:0.02em',
  ].join(';')
  document.body.appendChild(el)
  return el
}

function showTooltip(tt: HTMLDivElement, e: MouseEvent, d: D3Node) {
  const ppr = d.ppr_score || 0
  const sc  = ppr > 0 ? ppr.toFixed(5) : '—'
  const seedPart = d.is_seed ? ` · seed_w=${(d.seed_weight || 0).toFixed(3)}` : ''
  const name = d.name || d.file_path?.split('/').pop() || d.id?.split('::').pop() || '?'
  tt.innerHTML = `
    <div style="font-weight:600;color:var(--text);margin-bottom:2px;word-break:break-all">${name}</div>
    <div style="color:var(--text-muted);font-size:9px;margin-bottom:3px;word-break:break-all">${d.file_path ?? ''}</div>
    <div style="font-variant-numeric:tabular-nums slashed-zero;color:var(--text-dim);font-size:9px">ppr=${sc}${seedPart}</div>
  `
  tt.style.display = 'block'
  tt.style.left = `${e.clientX + 14}px`
  tt.style.top  = `${e.clientY - 28}px`
}
function moveTooltip(tt: HTMLDivElement, e: MouseEvent) {
  tt.style.left = `${e.clientX + 14}px`
  tt.style.top  = `${e.clientY - 28}px`
}
function hideTooltip(tt: HTMLDivElement) { tt.style.display = 'none' }

/* ── Main component ───────────────────────────────────────── */
export default function GraphCanvas({
  nodes, edges, onNodeSelect, selectedNode,
  dampingFactor = 0.70, topK = 30, projectHistory = [],
  isDatabaseEmpty = false
}: GraphCanvasProps) {
  const svgRef   = useRef<SVGSVGElement>(null)
  const simRef   = useRef<d3.Simulation<D3Node, D3Edge> | null>(null)
  const zoomRef  = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const sizeRef  = useRef({ w: 800, h: 600 })
  const ttRef    = useRef<HTMLDivElement | null>(null)
  const rafRef   = useRef<number>()
  const scaleRef = useRef(1)

  const [hiddenNodeTypes, setHiddenNodeTypes] = useState<Set<string>>(new Set())
  const [hiddenEdgeTypes, setHiddenEdgeTypes] = useState<Set<string>>(new Set())

  const filteredNodes = useMemo(() => 
    nodes.filter(n => !hiddenNodeTypes.has(n.label.toLowerCase())),
    [nodes, hiddenNodeTypes]
  )
  
  const filteredEdges = useMemo(() => 
    edges.filter(e => {
      let typeKey = e.type.toLowerCase()
      if (typeKey === 'inherits_from') typeKey = 'inherits'
      return !hiddenEdgeTypes.has(typeKey)
    }),
    [edges, hiddenEdgeTypes]
  )

  /* ResizeObserver */
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const parent = svg.parentElement
    if (!parent) return
    const ro = new ResizeObserver(entries => {
      if (!entries[0]) return
      const { width, height } = entries[0].contentRect
      sizeRef.current = { w: Math.floor(width), h: Math.floor(height) }
    })
    ro.observe(parent)
    return () => ro.disconnect()
  }, [])

  /* Build graph */
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return

    const tt = createTooltipEl()
    ttRef.current = tt

    d3.select(svg).selectAll('*').remove()
    if (simRef.current) { simRef.current.stop(); simRef.current = null }
    if (rafRef.current) cancelAnimationFrame(rafRef.current)

    if (!filteredNodes.length) {
      return () => { tt.remove(); ttRef.current = null }
    }

    const parent = svg.parentElement
    const rect   = parent?.getBoundingClientRect()
    const W = sizeRef.current.w || rect?.width  || 800
    const H = sizeRef.current.h || rect?.height || 600

    const svgSel = d3.select(svg)
    const defs   = svgSel.append('defs')

    /* Glow filter */
    const glow = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-80%').attr('y', '-80%')
      .attr('width', '260%').attr('height', '260%')
    glow.append('feGaussianBlur').attr('stdDeviation', '2.5').attr('result', 'coloredBlur')
    const glowMerge = glow.append('feMerge')
    glowMerge.append('feMergeNode').attr('in', 'coloredBlur')
    glowMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    /* Arrow markers */
    EDGE_TYPES.forEach(rel => {
      const color = edgeColor(rel)
      ;[['arr', color, 1], ['arr-dim', color, 0.06]].forEach(([id, fill, opacity]) => {
        defs.append('marker')
          .attr('id', `${id}-${rel}`)
          .attr('viewBox', '0 -4 8 8')
          .attr('refX', 18).attr('refY', 0)
          .attr('markerWidth', 5).attr('markerHeight', 5)
          .attr('orient', 'auto')
          .append('path')
          .attr('d', 'M0,-4L8,0L0,4')
          .attr('fill', fill as string)
          .attr('fill-opacity', opacity as number)
      })
    })

    const g    = svgSel.append('g')
    
    // Inherit existing transform to prevent jumps on touch
    const currentTransform = d3.zoomTransform(svg)
    g.attr('transform', currentTransform.toString())
    scaleRef.current = currentTransform.k

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 6])
      .on('zoom', e => {
        g.attr('transform', e.transform)
        scaleRef.current = e.transform.k
        // update scale corner tick
        const scaleTick = svg.parentElement?.querySelector('.lattice-scale-tick') as HTMLElement | null
        if (scaleTick) scaleTick.textContent = `scale: ${e.transform.k.toFixed(2)}×`
      })
    
    svgSel.call(zoom)
    // Synchronize zoom state if it was already modified
    svgSel.call(zoom.transform, currentTransform)
    
    zoomRef.current = zoom

    const nodeById: Record<string, D3Node> = {}
    filteredNodes.forEach(n => { nodeById[n.id] = n })

    const links: D3Edge[] = filteredEdges
      .map(e => ({
        source: nodeById[e.source as string] ?? e.source,
        target: nodeById[e.target as string] ?? e.target,
        type: e.type,
      }))
      .filter(e =>
        e.source && e.target &&
        typeof e.source === 'object' &&
        typeof e.target === 'object',
      )

    /* Edges */
    const linkSel = g.append('g')
      .selectAll<SVGLineElement, D3Edge>('line')
      .data(links)
      .join('line')
      .attr('stroke', d => edgeColor(d.type))
      .attr('stroke-width', 1.1)
      .attr('stroke-opacity', 0.38)
      .attr('marker-end', d => `url(#arr-${d.type})`)

    /* Particles */
    const particleGroup  = g.append('g')
    const animatedLinks  = links.filter(l => l.type === 'CALLS' || l.type === 'IMPORTS')
    const particles      = particleGroup
      .selectAll<SVGCircleElement, D3Edge>('circle.particle')
      .data(animatedLinks)
      .join('circle')
      .attr('class', 'particle')
      .attr('r', 1.8)
      .attr('fill', d => edgeColor(d.type))
      .attr('opacity', 0.85)

    const t0 = Date.now()
    const animate = () => {
      const elapsed = (Date.now() - t0) % 2000
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
      rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)

    const nodeGroup = g.append('g')

    /* Seed rings */
    const seedRings = nodeGroup
      .selectAll<SVGCircleElement, D3Node>('circle.seed-ring')
      .data(filteredNodes.filter(d => d.is_seed))
      .join('circle')
      .attr('class', 'seed-ring')
      .attr('r', d => nodeRadius(d) + 5)
      .attr('fill', 'none')
      .attr('stroke', 'var(--seed)')
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '3 3')
      .attr('stroke-opacity', 0.7)
      .attr('pointer-events', 'none')

    seedRings.append('animate')
      .attr('attributeName', 'stroke-opacity')
      .attr('values', '0.7;0.15;0.7')
      .attr('dur', '2s')
      .attr('repeatCount', 'indefinite')

    /* Node circles */
    const nodeSel = nodeGroup
      .selectAll<SVGCircleElement, D3Node>('circle.node')
      .data(filteredNodes)
      .join('circle')
      .attr('class', 'node')
      .attr('r', nodeRadius)
      .attr('fill', d => nodeColor(d.label))
      .attr('stroke', 'var(--bg)')
      .attr('stroke-width', 1.5)
      .attr('filter', d => (d.ppr_score || 0) > 0.05 ? 'url(#glow)' : null)
      .attr('cursor', 'pointer')
      .on('click', (_e, d) => onNodeSelect(d))
      .on('mouseover', (_e, d) => showTooltip(tt, _e as unknown as MouseEvent, d))
      .on('mousemove', e => moveTooltip(tt, e as unknown as MouseEvent))
      .on('mouseout', () => hideTooltip(tt))

    /* Labels */
    const labelSel = g.append('g')
      .selectAll<SVGTextElement, D3Node>('text')
      .data(filteredNodes)
      .join('text')
      .text(d => d.name || d.file_path?.split('/').pop() || d.id?.split('::').pop() || '?')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', d => d.is_seed || (d.ppr_score || 0) > 0.05 ? 10 : 8.5)
      .attr('fill', 'var(--text)')
      .attr('opacity', d => {
        if (d.is_seed || (d.ppr_score || 0) > 0.04) return 0.9
        return 0.35
      })
      .attr('text-anchor', 'middle')
      .attr('dy', d => nodeRadius(d) + 14)
      .attr('pointer-events', 'none')
      .attr('letter-spacing', '0.04em')
      .style('text-shadow', '0 1px 4px var(--bg), 0 0 6px var(--bg)')

    /* Simulation */
    const sim = d3.forceSimulation<D3Node, D3Edge>(filteredNodes)
      .force('link', d3.forceLink<D3Node, D3Edge>(links).id(d => d.id).distance(100).strength(0.25))
      .force('charge', d3.forceManyBody<D3Node>().strength(-220))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide<D3Node>().radius(d => nodeRadius(d) + 8))
      .on('tick', () => {
        linkSel
          .attr('x1', d => (d.source as D3Node).x ?? 0)
          .attr('y1', d => (d.source as D3Node).y ?? 0)
          .attr('x2', d => (d.target as D3Node).x ?? 0)
          .attr('y2', d => (d.target as D3Node).y ?? 0)
        nodeSel.attr('cx', d => d.x ?? 0).attr('cy', d => d.y ?? 0)
        seedRings.attr('cx', d => d.x ?? 0).attr('cy', d => d.y ?? 0)
        labelSel.attr('x', d => d.x ?? 0).attr('y', d => d.y ?? 0)
      })

    nodeSel.call(
      d3.drag<SVGCircleElement, D3Node>()
        .on('start', (e, d) => {
          if (!e.active) sim.alphaTarget(0.3).restart()
          d.fx = d.x; d.fy = d.y
        })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d) => {
          if (!e.active) sim.alphaTarget(0)
          d.fx = null; d.fy = null
        }),
    )

    simRef.current = sim

    return () => {
      sim.stop()
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      hideTooltip(tt)
      tt.remove()
      ttRef.current = null
    }
  }, [filteredNodes, filteredEdges, onNodeSelect])

  /* Selection highlight */
  useEffect(() => {
    if (!svgRef.current) return
    const svg         = d3.select(svgRef.current)
    const nodeSel     = svg.selectAll<SVGCircleElement, D3Node>('circle.node')
    const linkSel     = svg.selectAll<SVGLineElement, D3Edge>('line')
    const labelSel    = svg.selectAll<SVGTextElement, D3Node>('text')
    const ringSel     = svg.selectAll<SVGCircleElement, D3Node>('circle.seed-ring')
    const particleSel = svg.selectAll<SVGCircleElement, D3Edge>('circle.particle')

    if (!selectedNode) {
      nodeSel.attr('opacity', 1)
      ringSel.attr('opacity', 1)
      linkSel.attr('stroke-opacity', 0.38).attr('marker-end', d => `url(#arr-${d.type})`)
      labelSel.attr('opacity', d => d.is_seed || (d.ppr_score || 0) > 0.04 ? 0.9 : 0.35)
      particleSel.attr('opacity', 0.85).attr('r', 1.8)
      return
    }

    const pathNodeIds = new Set<string>(selectedNode.reasoning_path || [])
    const isPathActive = pathNodeIds.size > 0

    const connected = new Set<string>([selectedNode.id])
    if (!isPathActive) {
      filteredEdges.forEach(e => {
        const sid = typeof e.source === 'object' ? (e.source as D3Node).id : e.source
        const tid = typeof e.target === 'object' ? (e.target as D3Node).id : e.target
        if (sid === selectedNode.id) connected.add(tid as string)
        if (tid === selectedNode.id) connected.add(sid as string)
      })
    }

    const highlightIds = isPathActive ? pathNodeIds : connected

    nodeSel.attr('opacity', d => highlightIds.has(d.id) ? 1 : (isPathActive ? 0.15 : 0.06))
    ringSel.attr('opacity', d => highlightIds.has(d.id) ? 1 : 0)
    labelSel.attr('opacity', d => highlightIds.has(d.id) ? 0.9 : (isPathActive ? 0.1 : 0.04))

    linkSel
      .attr('stroke-opacity', d => {
        const sid = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
        const tid = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
        if (isPathActive) {
          return (pathNodeIds.has(sid as string) && pathNodeIds.has(tid as string)) ? 1.0 : 0.05
        }
        return (sid === selectedNode.id || tid === selectedNode.id) ? 1.0 : 0.04
      })
      .attr('stroke-width', d => {
        if (isPathActive) {
          const sid = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
          const tid = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
          return (pathNodeIds.has(sid as string) && pathNodeIds.has(tid as string)) ? 2.5 : 1.1
        }
        return 1.1
      })
      .attr('filter', d => {
        if (isPathActive) {
          const sid = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
          const tid = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
          return (pathNodeIds.has(sid as string) && pathNodeIds.has(tid as string)) ? 'url(#glow)' : null
        }
        return null
      })
      .attr('marker-end', d => {
        const sid = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
        const tid = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
        if (isPathActive) {
          return (pathNodeIds.has(sid as string) && pathNodeIds.has(tid as string))
            ? `url(#arr-${d.type})`
            : `url(#arr-dim-${d.type})`
        }
        return (sid === selectedNode.id || tid === selectedNode.id)
          ? `url(#arr-${d.type})`
          : `url(#arr-dim-${d.type})`
      })

    particleSel
      .attr('opacity', d => {
        const sid = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
        const tid = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
        if (isPathActive) {
          return (pathNodeIds.has(sid as string) && pathNodeIds.has(tid as string)) ? 1.0 : 0.05
        }
        return (sid === selectedNode.id || tid === selectedNode.id) ? 1.0 : 0.04
      })
      .attr('r', d => {
        const sid = typeof d.source === 'object' ? (d.source as D3Node).id : d.source
        const tid = typeof d.target === 'object' ? (d.target as D3Node).id : d.target
        if (isPathActive) {
          return (pathNodeIds.has(sid as string) && pathNodeIds.has(tid as string)) ? 3 : 1.8
        }
        return (sid === selectedNode.id || tid === selectedNode.id) ? 3 : 1.8
      })

    const sn = filteredNodes.find(n => n.id === selectedNode.id)
    if (sn?.x !== undefined && sn?.y !== undefined && zoomRef.current) {
      const { w: W, h: H } = sizeRef.current
      // Soften the zoom level — 1.4 is a good balance between focus and context
      const scale = 1.4
      d3.select(svgRef.current!)
        .transition().duration(750)
        .call(
          zoomRef.current.transform,
          d3.zoomIdentity.translate(W / 2 - sn.x * scale, H / 2 - sn.y * scale).scale(scale),
        )
    }
  }, [selectedNode, filteredNodes, filteredEdges])

  const hasData = nodes.length > 0

  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minWidth: 0, height: '100%' }}>
      {/* Subtle scale tick — bottom-left corner */}
      {hasData && (
        <div className="lattice-scale-tick" style={cornerTick({ bottom: 8, right: 8 })}>
          scale: 1.00×
        </div>
      )}

      {/* Empty state / Onboarding */}
      {isDatabaseEmpty && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--surface2)', padding: 32, border: '1px solid var(--border)', borderRadius: 8, width: 440 }}>
            <h2 style={{ margin: '0 0 16px', fontSize: 16, color: 'var(--text)' }}>Welcome to CodeGraph</h2>
            
            {projectHistory.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>Previous Projects</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {projectHistory.map((proj, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        initializeProject(proj.url || proj.path).then(() => window.location.reload())
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 12px',
                        background: 'var(--surface)',
                        border: '1px solid var(--border)',
                        borderRadius: 4,
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'border-color 120ms'
                      }}
                      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>{proj.name}</span>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{proj.url || proj.path}</span>
                      </div>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>→</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <h3 style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>Index New Repository</h3>
            <form onSubmit={(e) => {
              e.preventDefault()
              const target = (e.currentTarget.elements.namedItem('target') as HTMLInputElement).value
              
              const btn = e.currentTarget.querySelector('button')
              if (btn) {
                btn.disabled = true
                btn.textContent = 'Indexing...'
              }
              
              initializeProject(target).then(() => window.location.reload()).catch(err => {
                alert('Failed to initialize: ' + err)
                if (btn) {
                  btn.disabled = false
                  btn.textContent = 'Index Repository'
                }
              })
            }}>
              <input 
                name="target"
                placeholder="e.g., . or https://github.com/user/repo"
                style={{ width: '100%', padding: '8px 12px', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', marginBottom: 16, fontFamily: 'var(--font-mono)', fontSize: 11 }}
              />
              <button type="submit" style={{ width: '100%', padding: '10px', background: 'var(--accent)', color: 'var(--bg)', border: 'none', fontWeight: 600, cursor: 'pointer' }}>
                Index Repository
              </button>
            </form>
          </div>
        </div>
      )}

      <svg
        ref={svgRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          background: 'transparent',
        }}
      />

      {/* Graph overlays */}
      {!isDatabaseEmpty && (
        <>
          <PPRReadout
            nodeCount={filteredNodes.length}
            edgeCount={filteredEdges.length}
            seedCount={filteredNodes.filter(n => n.is_seed).length}
            dampingFactor={dampingFactor}
            topK={topK}
          />
          <LatticeLegend 
            hiddenNodeTypes={hiddenNodeTypes} 
            setHiddenNodeTypes={setHiddenNodeTypes}
            hiddenEdgeTypes={hiddenEdgeTypes}
            setHiddenEdgeTypes={setHiddenEdgeTypes}
          />
        </>
      )}
    </div>
  )
}

/* ── Corner tick helper ──────────────────────────────────── */
function cornerTick(pos: React.CSSProperties): React.CSSProperties {
  return {
    position: 'absolute',
    fontSize: 8.5,
    color: 'var(--text-muted)',
    letterSpacing: '0.10em',
    fontVariantNumeric: 'tabular-nums',
    fontFamily: 'var(--font-mono)',
    pointerEvents: 'none',
    ...pos,
  }
}

/* ── PPR Readout panel ───────────────────────────────────── */
function PPRReadout({
  nodeCount, edgeCount, seedCount, dampingFactor, topK,
}: {
  nodeCount: number
  edgeCount: number
  seedCount: number
  dampingFactor: number
  topK: number
}) {
  const [open, setOpen] = useState(false)

  const rows: [string, string, boolean][] = [
    ['nodes', nodeCount.toLocaleString(), false],
    ['edges', edgeCount.toLocaleString(), false],
    ['seeds', String(seedCount), false],
    ['α (damping)', dampingFactor.toFixed(3), false],
    ['top_k limit', String(topK), false],
  ]

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          background: 'color-mix(in oklch, var(--surface) 50%, transparent)',
          backdropFilter: 'blur(4px)',
          border: '1px solid var(--border)',
          padding: '4px 8px',
          fontSize: 8.5,
          color: 'var(--text-dim)',
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.10em',
          textTransform: 'uppercase',
          cursor: 'pointer',
          borderRadius: 2,
        }}
      >
        ppr.readout +
      </button>
    )
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        right: 12,
        background: 'color-mix(in oklch, var(--surface) 92%, transparent)',
        backdropFilter: 'blur(10px)',
        border: '1px solid var(--border)',
        minWidth: 180,
        fontSize: 10,
        boxShadow: 'var(--shadow)',
      }}
    >
      <button
        onClick={() => setOpen(false)}
        style={{
          width: '100%',
          padding: '8px 12px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 8,
          background: 'transparent',
          border: 'none',
          borderBottom: '1px dashed var(--border)',
          color: 'var(--text-muted)',
          fontSize: 9,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.16em',
          textTransform: 'uppercase',
          cursor: 'pointer',
        }}
      >
        <span>▸ ppr.readout</span>
        <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>–</span>
      </button>

      <div style={{ padding: '8px 12px' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto',
            gap: '4px 12px',
          }}
        >
          {rows.map(([label, value, accent]) => (
            <div key={label} style={{ display: 'contents' }}>
              <span style={{ color: 'var(--text-dim)' }}>{label}</span>
              <span
                style={{
                  color: accent ? 'var(--accent)' : 'var(--text)',
                  fontVariantNumeric: 'tabular-nums',
                  textAlign: 'right',
                }}
              >
                {value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


/* ── Legend ──────────────────────────────────────────────── */
function LatticeLegend({
  hiddenNodeTypes, setHiddenNodeTypes,
  hiddenEdgeTypes, setHiddenEdgeTypes
}: {
  hiddenNodeTypes: Set<string>
  setHiddenNodeTypes: React.Dispatch<React.SetStateAction<Set<string>>>
  hiddenEdgeTypes: Set<string>
  setHiddenEdgeTypes: React.Dispatch<React.SetStateAction<Set<string>>>
}) {
  const [open, setOpen] = useState(true)

  const nodeTypes: [string, string][] = [
    ['file', 'var(--node-file)'],
    ['class', 'var(--node-class)'],
    ['function', 'var(--node-function)'],
    ['method', 'var(--node-method)'],
  ]
  const edgeTypes: [string, string][] = [
    ['CALLS', 'var(--edge-calls)'],
    ['IMPORTS', 'var(--edge-imports)'],
    ['CONTAINS', 'var(--edge-contains)'],
    ['INHERITS', 'var(--edge-inherits)'],
  ]

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: 'absolute',
          bottom: 12,
          left: 12,
          background: 'color-mix(in oklch, var(--surface) 88%, transparent)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border)',
          padding: '6px 10px',
          fontSize: 9,
          color: 'var(--text-muted)',
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          fontFamily: 'var(--font-mono)',
          cursor: 'pointer',
        }}
      >
        ▸ legend +
      </button>
    )
  }

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 12,
        left: 12,
        background: 'color-mix(in oklch, var(--surface) 88%, transparent)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--border)',
        fontSize: 9,
      }}
    >
      <button
        onClick={() => setOpen(false)}
        style={{
          width: '100%',
          padding: '6px 10px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 8,
          background: 'transparent',
          border: 'none',
          borderBottom: '1px dashed var(--border)',
          color: 'var(--text-muted)',
          fontSize: 9,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          cursor: 'pointer',
        }}
      >
        <span>▸ legend</span>
        <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>–</span>
      </button>
      <div style={{ display: 'flex', gap: 16, padding: 10 }}>
      <div>
        <div
          style={{
            color: 'var(--text-muted)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginBottom: 4,
          }}
        >
          nodes
        </div>
        {nodeTypes.map(([label, color]) => {
          const isHidden = hiddenNodeTypes.has(label)
          return (
            <div
              key={label}
              style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, cursor: 'pointer', opacity: isHidden ? 0.4 : 1 }}
              onClick={() => {
                setHiddenNodeTypes(prev => {
                  const next = new Set(prev)
                  if (next.has(label)) next.delete(label)
                  else next.add(label)
                  return next
                })
              }}
            >
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: color }} />
              <div style={{ color: 'var(--text-dim)' }}>{label}</div>
            </div>
          )
        })}
      </div>
      <div>
        <div
          style={{
            color: 'var(--text-muted)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginBottom: 4,
          }}
        >
          edges
        </div>
        {edgeTypes.map(([label, color]) => {
          const isHidden = hiddenEdgeTypes.has(label.toLowerCase())
          return (
            <div
              key={label}
              style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, cursor: 'pointer', opacity: isHidden ? 0.4 : 1 }}
              onClick={() => {
                setHiddenEdgeTypes(prev => {
                  const next = new Set(prev)
                  const key = label.toLowerCase()
                  if (next.has(key)) next.delete(key)
                  else next.add(key)
                  return next
                })
              }}
            >
              <div style={{ width: 16, height: 1.5, background: color }} />
              <div style={{ color: 'var(--text-dim)' }}>{label}</div>
            </div>
          )
        })}
      </div>
      </div>
    </div>
  )
}

