import { useEffect, useRef, useState, useMemo } from 'react'
import * as d3 from 'd3'
import type { D3Node, D3Edge } from '../../types/graph'
import type { GraphNode } from '../../types/api'
import {
  fileNodeIds,
  fitGraphToView,
  zoomByFactor,
  resolveThemeColors,
  type GraphColors,
} from './graphHelpers'
import { nodeRadius, appendNodeShape } from './graphShapes'
import { drawScene, sizeCanvas, type HighlightState } from './canvasRenderer'
import { initializeProject, ProjectHistoryItem } from '../../api/client'
import type { WSStatus } from '../../hooks/useWebSocket'
import { useTheme } from '../../context/ThemeContext'
import GraphControls from './GraphControls'

interface GraphCanvasProps {
  nodes: D3Node[]
  edges: D3Edge[]
  onNodeSelect: (node: GraphNode | null) => void
  selectedNode?: GraphNode | null
  highlightFilePath?: string | null
  pathHighlightIds?: string[]
  viewMode?: 'full' | 'query' | 'focus'
  dampingFactor?: number
  topK?: number
  showPprReadout?: boolean
  fitViewKey?: number
  fileFocusKey?: number
  projectHistory?: ProjectHistoryItem[]
  isDatabaseEmpty?: boolean
  rebuildActive?: boolean
  rebuildMessage?: WSStatus | null
}

const PARTICLE_MAX_EDGES = 500
/** Stable empty default — avoids re-running highlight effect when no path is active. */
const EMPTY_PATH_HIGHLIGHT: string[] = []
/* Level-of-detail zoom thresholds (in transform scale k). */
const LOD_PARTICLE_SCALE = 0.5
const LOD_LABEL_SCALE = 0.7
const LOD_ARROW_SCALE = 0.85
/* Above this many glowing nodes, skip the SVG glow filter (avoids flicker). */
const GLOW_NODE_LIMIT = 80

/* ── Tooltip ──────────────────────────────────────────────── */
function createTooltipEl(): HTMLDivElement {
  const el = document.createElement('div')
  el.style.cssText = [
    'position:fixed',
    'background:var(--overlay)',
    'backdrop-filter:blur(12px)',
    '-webkit-backdrop-filter:blur(12px)',
    'border:1px solid var(--border)',
    'border-radius:var(--radius-md)',
    'padding:9px 12px 9px 13px',
    'pointer-events:none',
    'z-index:999',
    'max-width:300px',
    'font-size:11px',
    'font-family:var(--font-mono)',
    'display:none',
    'box-shadow:var(--elev-2)',
  ].join(';')
  document.body.appendChild(el)
  return el
}

const NODE_TYPE_VAR: Record<string, string> = {
  File: '--node-file',
  Class: '--node-class',
  Function: '--node-function',
  Method: '--node-method',
}

function showTooltip(tt: HTMLDivElement, e: MouseEvent, d: D3Node) {
  const ppr = d.ppr_score || 0
  const sc  = ppr > 0 ? ppr.toFixed(5) : '—'
  const seedPart = d.is_seed ? ` · seed_w=${(d.seed_weight || 0).toFixed(3)}` : ''
  const name = d.name || d.file_path?.split('/').pop() || d.id?.split('::').pop() || '?'
  const dotVar = NODE_TYPE_VAR[d.label] ?? '--text-muted'
  tt.innerHTML = `
    <div style="display:flex;align-items:center;gap:7px;margin-bottom:3px">
      <span style="width:8px;height:8px;border-radius:2px;flex:none;background:var(${dotVar});box-shadow:0 0 6px color-mix(in oklch, var(${dotVar}) 60%, transparent)"></span>
      <span style="font-weight:600;color:var(--text);word-break:break-all">${name}</span>
      <span style="margin-left:auto;font-size:8px;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-muted)">${d.label ?? ''}</span>
    </div>
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
function rebuildStatusLabel(msg: WSStatus | null | undefined): string {
  if (!msg || msg.type !== 'rebuild_progress') return 'Indexing…'
  if (msg.stage === 'parsing') {
    const n = msg.files_parsed ?? 0
    const t = msg.files_total ?? '?'
    const file = msg.current_file ? ` · ${msg.current_file}` : ''
    return `Parsing ${n}/${t}${file}`
  }
  return `Building · ${msg.node_count ?? 0} nodes · ${msg.edge_count ?? 0} edges`
}

export default function GraphCanvas({
  nodes, edges, onNodeSelect, selectedNode,
  highlightFilePath = null,
  pathHighlightIds = EMPTY_PATH_HIGHLIGHT,
  viewMode = 'full',
  dampingFactor = 0.70, topK = 10, showPprReadout = false, fitViewKey = 0,
  fileFocusKey = 0,
  projectHistory = [],
  isDatabaseEmpty = false,
  rebuildActive = false,
  rebuildMessage = null,
}: GraphCanvasProps) {
  const [initError, setInitError] = useState<string | null>(null)
  const [indexing, setIndexing] = useState(false)
  const isIndexing = indexing || rebuildActive
  const indexLabel = rebuildActive ? rebuildStatusLabel(rebuildMessage) : 'Index Repository'

  useEffect(() => {
    if (!rebuildActive) setIndexing(false)
  }, [rebuildActive])

  const { theme } = useTheme()

  const svgRef    = useRef<SVGSVGElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const simRef    = useRef<d3.Simulation<D3Node, D3Edge> | null>(null)
  const zoomRef   = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const sizeRef   = useRef({ w: 800, h: 600 })
  const ttRef     = useRef<HTMLDivElement | null>(null)
  const rafRef    = useRef<number>(0)
  const scaleRef  = useRef(1)

  /* Canvas/render state shared across effects. */
  const colorsRef        = useRef<GraphColors | null>(null)
  const dprRef           = useRef(1)
  const linksRef         = useRef<D3Edge[]>([])
  const particleLinksRef = useRef<D3Edge[]>([])
  const transformRef     = useRef<d3.ZoomTransform>(d3.zoomIdentity)
  const highlightRef     = useRef<HighlightState | null>(null)
  const simRunningRef    = useRef(false)
  const requestDrawRef   = useRef<(() => void) | null>(null)
  const labelShowAllRef  = useRef(true)
  const labelSelRef       = useRef<d3.Selection<SVGTextElement, D3Node, SVGGElement, unknown> | null>(null)
  const onNodeSelectRef   = useRef(onNodeSelect)

  useEffect(() => { onNodeSelectRef.current = onNodeSelect })

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
      const w = Math.floor(width)
      const h = Math.floor(height)
      sizeRef.current = { w, h }
      if (canvasRef.current) sizeCanvas(canvasRef.current, w, h, dprRef.current)
      requestDrawRef.current?.()
    })
    ro.observe(parent)
    return () => ro.disconnect()
  }, [])

  /* Build graph */
  useEffect(() => {
    const svg = svgRef.current
    const canvas = canvasRef.current
    if (!svg || !canvas) return

    const tt = createTooltipEl()
    ttRef.current = tt

    d3.select(svg).selectAll('*').remove()
    if (simRef.current) { simRef.current.stop(); simRef.current = null }
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = 0
    highlightRef.current = null
    simRunningRef.current = false

    const dpr = window.devicePixelRatio || 1
    dprRef.current = dpr
    colorsRef.current = resolveThemeColors()

    const ctx = canvas.getContext('2d')

    if (!filteredNodes.length) {
      linksRef.current = []
      particleLinksRef.current = []
      labelSelRef.current = null
      requestDrawRef.current = null
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
      return () => { tt.remove(); ttRef.current = null }
    }

    const parent = svg.parentElement
    const rect   = parent?.getBoundingClientRect()
    const W = sizeRef.current.w || rect?.width  || 800
    const H = sizeRef.current.h || rect?.height || 600
    sizeRef.current = { w: W, h: H }
    sizeCanvas(canvas, W, H, dpr)

    const svgSel = d3.select(svg)
    const defs   = svgSel.append('defs')

    /* Glow filter (nodes only; gated by count to avoid filter flicker) */
    const glow = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-80%').attr('y', '-80%')
      .attr('width', '260%').attr('height', '260%')
    glow.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur')
    const glowMerge = glow.append('feMerge')
    glowMerge.append('feMergeNode').attr('in', 'coloredBlur')
    glowMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    /* Radial-gradient node fills for a soft volumetric look. */
    const NODE_GRAD_VARS: Record<string, string> = {
      File: '--node-file',
      Class: '--node-class',
      Function: '--node-function',
      Method: '--node-method',
      default: '--text-muted',
    }
    Object.entries(NODE_GRAD_VARS).forEach(([label, cssVar]) => {
      const grad = defs.append('radialGradient')
        .attr('id', `node-grad-${label}`)
        .attr('cx', '35%').attr('cy', '28%').attr('r', '78%')
      grad.append('stop').attr('offset', '0%')
        .style('stop-color', `color-mix(in oklch, var(${cssVar}) 70%, white)`)
      grad.append('stop').attr('offset', '55%')
        .style('stop-color', `var(${cssVar})`)
      grad.append('stop').attr('offset', '100%')
        .style('stop-color', `color-mix(in oklch, var(${cssVar}) 82%, black)`)
    })

    const g    = svgSel.append('g')

    // Inherit existing transform to prevent jumps on touch
    const currentTransform = d3.zoomTransform(svg)
    g.attr('transform', currentTransform.toString())
    scaleRef.current = currentTransform.k
    transformRef.current = currentTransform

    /* Toggle label visibility on a LOD threshold crossing (cheap, rare). */
    const applyLabelLOD = (k: number, force = false) => {
      const showAll = k >= LOD_LABEL_SCALE
      if (!force && showAll === labelShowAllRef.current) return
      labelShowAllRef.current = showAll
      labelSelRef.current?.attr('display', d =>
        showAll || d.is_seed || (d.ppr_score || 0) > 0.04 ? null : 'none',
      )
    }

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 6])
      .on('zoom', e => {
        g.attr('transform', e.transform)
        scaleRef.current = e.transform.k
        transformRef.current = e.transform
        applyLabelLOD(e.transform.k)
        const scaleTick = svg.parentElement?.querySelector('.lattice-scale-tick') as HTMLElement | null
        if (scaleTick) scaleTick.textContent = `scale: ${e.transform.k.toFixed(2)}×`
        // Routed through the ref so the synchronous zoom.transform() call during
        // build (before draw/loop are wired) is a safe no-op.
        requestDrawRef.current?.()
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
    linksRef.current = links

    /* Particles on CALLS / IMPORTS only — rendered on canvas. */
    const animatedLinks = links.filter(l => l.type === 'CALLS' || l.type === 'IMPORTS')
    const enableParticles = animatedLinks.length <= PARTICLE_MAX_EDGES
    particleLinksRef.current = enableParticles ? animatedLinks : []

    /* Glow LOD: skip per-node SVG filter on dense result sets. */
    const glowCount = filteredNodes.filter(
      d => (d.ppr_score || 0) > 0.05 || d.is_seed,
    ).length
    const enableGlow = glowCount <= GLOW_NODE_LIMIT

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

    /* Node shapes */
    const nodeSel = nodeGroup
      .selectAll<SVGGElement, D3Node>('g.node')
      .data(filteredNodes)
      .join('g')
      .attr('class', 'node')
      .attr('cursor', 'pointer')
      .on('click', (_e, d) => onNodeSelectRef.current(d))
      .on('mouseover', (_e, d) => showTooltip(tt, _e as unknown as MouseEvent, d))
      .on('mousemove', e => moveTooltip(tt, e as unknown as MouseEvent))
      .on('mouseout', () => hideTooltip(tt))

    appendNodeShape(nodeSel, enableGlow)

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
    labelSelRef.current = labelSel
    labelShowAllRef.current = true
    applyLabelLOD(currentTransform.k, true)

    /* Canvas render loop (edges + particles) and SVG position sync. */
    const t0 = Date.now()
    const draw = () => {
      const c = colorsRef.current
      if (!ctx || !c) return
      const t = transformRef.current
      const { w, h } = sizeRef.current
      drawScene(ctx, {
        links: linksRef.current,
        particleLinks: particleLinksRef.current,
        transform: { k: t.k, x: t.x, y: t.y },
        colors: c,
        dpr: dprRef.current,
        width: w,
        height: h,
        highlight: highlightRef.current,
        showParticles: particleLinksRef.current.length > 0 && t.k >= LOD_PARTICLE_SCALE,
        showArrows: t.k >= LOD_ARROW_SCALE,
        elapsed: Date.now() - t0,
        emphasizeStructural: viewMode === 'query' || viewMode === 'focus',
      })
      if (simRunningRef.current) {
        nodeSel.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
        seedRings.attr('cx', d => d.x ?? 0).attr('cy', d => d.y ?? 0)
        labelSel.attr('x', d => d.x ?? 0).attr('y', d => d.y ?? 0)
      }
    }

    const shouldAnimate = () =>
      simRunningRef.current ||
      (particleLinksRef.current.length > 0 && transformRef.current.k >= LOD_PARTICLE_SCALE)

    const loop = () => {
      draw()
      rafRef.current = shouldAnimate() ? requestAnimationFrame(loop) : 0
    }
    const requestDraw = () => {
      if (!rafRef.current) rafRef.current = requestAnimationFrame(loop)
    }
    requestDrawRef.current = requestDraw

    /* Simulation — tuned to settle quickly, then freeze the render loop. */
    const sim = d3.forceSimulation<D3Node, D3Edge>(filteredNodes)
      .force('link', d3.forceLink<D3Node, D3Edge>(links).id(d => d.id).distance(100).strength(0.25))
      .force('charge', d3.forceManyBody<D3Node>().strength(-220))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide<D3Node>().radius(d => nodeRadius(d) + 8))
      .velocityDecay(0.45)
      .alphaDecay(0.05)
      .on('tick', () => { simRunningRef.current = true; requestDraw() })
      .on('end', () => { simRunningRef.current = false; requestDraw() })

    simRunningRef.current = true
    requestDraw()

    nodeSel.call(
      d3.drag<SVGGElement, D3Node>()
        .on('start', (e, d) => {
          if (!e.active) sim.alphaTarget(0.3).restart()
          simRunningRef.current = true
          requestDraw()
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
      rafRef.current = 0
      simRunningRef.current = false
      requestDrawRef.current = null
      labelSelRef.current = null
      hideTooltip(tt)
      tt.remove()
      ttRef.current = null
    }
  }, [filteredNodes, filteredEdges, viewMode])

  const handleZoomIn = () => {
    const svg = svgRef.current
    const zoom = zoomRef.current
    if (!svg || !zoom) return
    const { w, h } = sizeRef.current
    zoomByFactor(svg, zoom, 1.35, w, h)
  }

  const handleZoomOut = () => {
    const svg = svgRef.current
    const zoom = zoomRef.current
    if (!svg || !zoom) return
    const { w, h } = sizeRef.current
    zoomByFactor(svg, zoom, 1 / 1.35, w, h)
  }

  const handleFitView = () => {
    const svg = svgRef.current
    const zoom = zoomRef.current
    if (!svg || !zoom || !filteredNodes.length) return
    const { w, h } = sizeRef.current
    fitGraphToView(svg, filteredNodes, zoom, w, h, {
      padding: 72,
      maxScale: 1.0,
      duration: 650,
    })
  }

  /* Selection / file / path highlight */
  useEffect(() => {
    if (!svgRef.current) return
    const svg      = d3.select(svgRef.current)
    const nodeSel  = svg.selectAll<SVGGElement, D3Node>('g.node')
    const labelSel = svg.selectAll<SVGTextElement, D3Node>('text')
    const ringSel  = svg.selectAll<SVGCircleElement, D3Node>('circle.seed-ring')

    const showAll = labelShowAllRef.current
    const baseLabelDisplay = (d: D3Node) =>
      showAll || d.is_seed || (d.ppr_score || 0) > 0.04 ? null : 'none'

    const resetStyles = () => {
      highlightRef.current = null
      nodeSel.attr('opacity', 1)
      ringSel.attr('opacity', 1)
      labelSel
        .attr('display', baseLabelDisplay)
        .attr('opacity', d => d.is_seed || (d.ppr_score || 0) > 0.04 ? 0.9 : 0.35)
        .style('font-weight', '400')
      requestDrawRef.current?.()
    }

    const externalPath = pathHighlightIds.length > 1
      ? new Set(pathHighlightIds)
      : null

    if (!selectedNode && !highlightFilePath && !externalPath) {
      resetStyles()
      return
    }

    let pathNodeIds = externalPath ?? new Set<string>()
    let isPathActive = pathNodeIds.size > 1
    let highlightIds = new Set<string>()
    let focusNodeId: string | null = null

    if (externalPath) {
      highlightIds = pathNodeIds
    } else if (selectedNode) {
      pathNodeIds = new Set(selectedNode.reasoning_path || [])
      isPathActive = pathNodeIds.size > 1
      const connected = new Set<string>([selectedNode.id])
      filteredEdges.forEach(e => {
        const sid = typeof e.source === 'object' ? (e.source as D3Node).id : e.source
        const tid = typeof e.target === 'object' ? (e.target as D3Node).id : e.target
        if (sid === selectedNode.id) connected.add(tid as string)
        if (tid === selectedNode.id) connected.add(sid as string)
      })
      highlightIds = isPathActive ? pathNodeIds : connected
      focusNodeId = selectedNode.id
    } else if (highlightFilePath) {
      highlightIds = fileNodeIds(highlightFilePath, filteredNodes)
      isPathActive = false
    }

    // Drive the canvas edge/particle layer via the shared highlight ref.
    highlightRef.current = { isPathActive, pathNodeIds, highlightIds }

    nodeSel.attr('opacity', d => highlightIds.has(d.id) ? 1 : (isPathActive ? 0.12 : 0.05))
    ringSel.attr('opacity', d => highlightIds.has(d.id) ? 1 : 0)
    labelSel
      .attr('display', d => highlightIds.has(d.id) ? null : baseLabelDisplay(d))
      .attr('opacity', d => {
        if (highlightIds.has(d.id)) return 1.0 // Active path labels are 100% visible
        return isPathActive ? 0.08 : 0.03
      })
      .style('font-weight', d => highlightIds.has(d.id) ? '600' : '400')

    requestDrawRef.current?.()

    if (focusNodeId && zoomRef.current && svgRef.current) {
      const { w: W, h: H } = sizeRef.current
      const focusNodes = filteredNodes.filter(
        n => highlightIds.has(n.id) && n.x !== undefined && n.y !== undefined,
      )
      const frame = focusNodes.length
        ? focusNodes
        : filteredNodes.filter(n => n.id === focusNodeId && n.x !== undefined)
      if (frame.length) {
        fitGraphToView(svgRef.current, frame, zoomRef.current, W, H, {
          padding: 96,
          maxScale: 1.6,
          duration: 700,
        })
      }
    }
  }, [selectedNode, highlightFilePath, pathHighlightIds, filteredNodes, filteredEdges])

  /* Recompute cached canvas colors on theme change (SVG uses CSS vars). */
  useEffect(() => {
    colorsRef.current = resolveThemeColors()
    requestDrawRef.current?.()
  }, [theme])

  /* Fit entire graph in view after restoring full codebase */
  useEffect(() => {
    if (!fitViewKey || !svgRef.current || !zoomRef.current || !filteredNodes.length) return
    const svg = svgRef.current
    const zoom = zoomRef.current
    const { w, h } = sizeRef.current
    const id = window.setTimeout(() => {
      fitGraphToView(svg, filteredNodes, zoom, w, h, {
        padding: 72,
        maxScale: 1.0,
        duration: 750,
      })
    }, 750)
    return () => window.clearTimeout(id)
  }, [fitViewKey, filteredNodes])

  /* Zoom to file cluster when selected from project tree */
  useEffect(() => {
    if (!fileFocusKey || !highlightFilePath || !svgRef.current || !zoomRef.current) return
    const svg = svgRef.current
    const zoom = zoomRef.current
    const { w, h } = sizeRef.current
    const ids = fileNodeIds(highlightFilePath, filteredNodes)
    const focusNodes = filteredNodes.filter(
      n => ids.has(n.id) && n.x !== undefined && n.y !== undefined,
    )
    if (!focusNodes.length) return
    const id = window.setTimeout(() => {
      fitGraphToView(svg, focusNodes, zoom, w, h, {
        padding: 96,
        maxScale: 1.5,
        duration: 700,
      })
    }, 350)
    return () => window.clearTimeout(id)
  }, [fileFocusKey, highlightFilePath, filteredNodes, filteredEdges])

  const hasData = nodes.length > 0

  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minWidth: 0, height: '100%' }}>
      {/* Background depth: radial vignette + faint static grid */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(120% 90% at 50% 38%, transparent 38%, var(--graph-vignette) 100%)',
        }}
      />
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          opacity: 0.5,
          backgroundImage:
            'radial-gradient(var(--graph-grid) 1px, transparent 1px)',
          backgroundSize: '30px 30px',
          maskImage:
            'radial-gradient(120% 90% at 50% 42%, black 30%, transparent 80%)',
          WebkitMaskImage:
            'radial-gradient(120% 90% at 50% 42%, black 30%, transparent 80%)',
        }}
      />

      {/* Subtle scale tick — bottom-left corner */}
      {hasData && !isDatabaseEmpty && (
        <GraphControls
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onFitView={handleFitView}
        />
      )}

      {hasData && (
        <div className="lattice-scale-tick font-mono" style={cornerTick({ bottom: 10, right: 10 })}>
          scale: 1.00×
        </div>
      )}

      {/* Empty state / Onboarding */}
      {isDatabaseEmpty && (
        <div style={{ position: 'absolute', inset: 0, zIndex: 20, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="surface-elevated" style={{ padding: 32, width: 440 }}>
            <h2 style={{ margin: '0 0 16px', fontSize: 18, color: 'var(--text)', fontFamily: 'var(--font-display)' }}>Welcome to CodeGraph</h2>
            
            {projectHistory.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>Previous Projects</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {projectHistory.map((proj, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setInitError(null)
                        setIndexing(true)
                        initializeProject(proj.url || proj.path)
                          .catch(err => { setInitError(String(err)); setIndexing(false) })
                      }}
                      disabled={isIndexing}
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
              
              setInitError(null)
              setIndexing(true)
              initializeProject(target)
                .catch(err => {
                  setInitError(String(err))
                  setIndexing(false)
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
              <button type="submit" disabled={isIndexing} style={{ width: '100%', padding: '10px', background: 'var(--accent)', color: 'var(--bg)', border: 'none', fontWeight: 600, cursor: 'pointer', opacity: isIndexing ? 0.6 : 1 }}>
                {isIndexing ? indexLabel : 'Index Repository'}
              </button>
            </form>
            {initError && (
              <div style={{ marginTop: 12, padding: 8, fontSize: 10, color: 'oklch(0.80 0.14 25)', border: '1px solid oklch(0.40 0.10 25)', background: 'oklch(0.22 0.05 25)' }}>
                {initError}
              </div>
            )}
          </div>
        </div>
      )}

      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          display: 'block',
          pointerEvents: 'none',
        }}
      />

      <svg
        ref={svgRef}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          display: 'block',
          background: 'transparent',
        }}
      />

      {/* Graph overlays */}
      {!isDatabaseEmpty && (
        <>
          {showPprReadout && (
            <PPRReadout
              nodeCount={filteredNodes.length}
              edgeCount={filteredEdges.length}
              seedCount={filteredNodes.filter(n => n.is_seed).length}
              dampingFactor={dampingFactor}
              topK={topK}
            />
          )}
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
    padding: '3px 7px',
    borderRadius: 'var(--radius-sm)',
    background: 'color-mix(in oklch, var(--surface) 55%, transparent)',
    border: '1px solid color-mix(in oklch, var(--border) 60%, transparent)',
    backdropFilter: 'blur(6px)',
    WebkitBackdropFilter: 'blur(6px)',
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
        className="surface-elevated"
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          padding: '6px 12px',
          fontSize: 11,
          color: 'var(--text-muted)',
          cursor: 'pointer',
        }}
      >
        PPR stats
      </button>
    )
  }

  return (
    <div
      className="surface-elevated"
      style={{
        position: 'absolute',
        top: 12,
        right: 12,
        minWidth: 180,
        fontSize: 11,
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
        <span>PPR stats</span>
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

  const nodeTypes: [string, string, NodeGlyph][] = [
    ['file', 'var(--node-file)', 'rect'],
    ['class', 'var(--node-class)', 'diamond'],
    ['function', 'var(--node-function)', 'circle'],
    ['method', 'var(--node-method)', 'hex'],
  ]
  const edgeTypes: [string, string, boolean][] = [
    ['CALLS', 'var(--edge-calls)', false],
    ['IMPORTS', 'var(--edge-imports)', false],
    ['CONTAINS', 'var(--edge-contains)', true],
    ['INHERITS', 'var(--edge-inherits)', true],
  ]

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="surface-elevated"
        style={{
          position: 'absolute',
          bottom: 12,
          right: 12,
          padding: '8px 12px',
          fontSize: 11,
          color: 'var(--text-muted)',
          cursor: 'pointer',
        }}
      >
        Legend
      </button>
    )
  }

  return (
    <div
      className="surface-elevated"
      style={{
        position: 'absolute',
        bottom: 12,
        right: 12,
        fontSize: 11,
        minWidth: 200,
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
          borderBottom: '1px solid var(--border)',
          color: 'var(--text)',
          fontSize: 12,
          fontWeight: 600,
          cursor: 'pointer',
          fontFamily: 'var(--font-body)',
        }}
      >
        <span>Legend</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>×</span>
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
        {nodeTypes.map(([label, color, glyph]) => {
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
              <NodeGlyphSwatch glyph={glyph} color={color} />
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
        {edgeTypes.map(([label, color, dashed]) => {
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
              <div
                style={{
                  width: 16,
                  height: 0,
                  borderTop: dashed ? `1.5px dashed ${color}` : `1.5px solid ${color}`,
                }}
              />
              <div style={{ color: 'var(--text-dim)' }}>{label}</div>
            </div>
          )
        })}
      </div>
      </div>
    </div>
  )
}

/* ── Legend node glyphs (mirror the canvas node shapes) ──── */
type NodeGlyph = 'rect' | 'diamond' | 'circle' | 'hex'

function NodeGlyphSwatch({ glyph, color }: { glyph: NodeGlyph; color: string }) {
  const common = { fill: color }
  return (
    <svg width="11" height="11" viewBox="-5 -5 10 10" style={{ flex: 'none', display: 'block' }}>
      {glyph === 'rect' && <rect x={-4} y={-3} width={8} height={6} rx={1.2} {...common} />}
      {glyph === 'diamond' && <polygon points="0,-4.5 4.5,0 0,4.5 -4.5,0" {...common} />}
      {glyph === 'circle' && <circle r={4} {...common} />}
      {glyph === 'hex' && (
        <polygon
          points={Array.from({ length: 6 }, (_, i) => {
            const a = (Math.PI / 3) * i - Math.PI / 6
            return `${(Math.cos(a) * 4.3).toFixed(2)},${(Math.sin(a) * 4.3).toFixed(2)}`
          }).join(' ')}
          {...common}
        />
      )}
    </svg>
  )
}

