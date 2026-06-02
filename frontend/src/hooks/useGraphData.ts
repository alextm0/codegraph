import { useMemo, useRef } from 'react'
import type { QueryResponse, GraphData as ApiGraphData, GraphNode } from '../types/api'
import type { D3Node, D3Edge } from '../types/graph'

interface GraphData {
  nodes: D3Node[]
  edges: D3Edge[]
  loading: boolean
  isDatabaseEmpty: boolean
  viewMode: 'full' | 'query' | 'focus'
}

type GraphViewMode = GraphData['viewMode']

const QUERY_FIELDS = ['ppr_score', 'is_seed', 'seed_weight', 'reasoning_path'] as const

/** Strip PPR / seed annotations so the full codebase graph renders uniformly. */
function stripQueryAnnotations(node: GraphNode): D3Node {
  const clean = { ...node } as D3Node
  clean.ppr_score = 0
  clean.is_seed = false
  clean.seed_weight = 0
  clean.reasoning_path = []
  return clean
}

export function useGraphData(
  response: QueryResponse | null,
  baseGraph: ApiGraphData | null,
  focusGraph: ApiGraphData | null = null,
  graphRevision = 0,
): GraphData {
  const nodeCacheRef = useRef<Map<string, D3Node>>(new Map())
  const viewModeRef = useRef<GraphViewMode>('full')
  const revisionRef = useRef(graphRevision)

  return useMemo(() => {
    const viewMode: GraphViewMode = focusGraph
      ? 'focus'
      : response?.graph
        ? 'query'
        : 'full'

    if (viewModeRef.current !== viewMode || revisionRef.current !== graphRevision) {
      nodeCacheRef.current.clear()
      viewModeRef.current = viewMode
      revisionRef.current = graphRevision
    }

    const activeGraph = focusGraph ?? response?.graph ?? baseGraph
    const isDatabaseEmpty = !baseGraph || (baseGraph.nodes.length === 0 && !response)
    const annotateQuery = viewMode === 'query' || viewMode === 'focus'

    if (!activeGraph) {
      return { nodes: [], edges: [], loading: false, isDatabaseEmpty, viewMode }
    }

    const nextNodes: D3Node[] = activeGraph.nodes.map(n => {
      if (!annotateQuery) {
        return stripQueryAnnotations(n)
      }

      const normalized = n as D3Node
      const cached = nodeCacheRef.current.get(n.id)
      if (cached) {
        return Object.assign(cached, normalized)
      }
      const newNode = { ...normalized }
      nodeCacheRef.current.set(n.id, newNode)
      return newNode
    })

    const nextIds = new Set(nextNodes.map(n => n.id))
    for (const id of nodeCacheRef.current.keys()) {
      if (!nextIds.has(id)) nodeCacheRef.current.delete(id)
    }

    const edges: D3Edge[] = activeGraph.edges.map(e => ({
      source: e.source,
      target: e.target,
      type: e.type,
    }))

    return { nodes: nextNodes, edges, loading: false, isDatabaseEmpty, viewMode }
  }, [response, baseGraph, focusGraph, graphRevision])
}

/** Fields cleared when leaving query view — used in tests. */
export function queryAnnotationFields(): readonly string[] {
  return QUERY_FIELDS
}
