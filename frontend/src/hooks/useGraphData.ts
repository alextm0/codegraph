import { useMemo, useRef } from 'react'
import type { QueryResponse, GraphData as ApiGraphData } from '../types/api'
import type { D3Node, D3Edge } from '../types/graph'

interface GraphData {
  nodes: D3Node[]
  edges: D3Edge[]
  loading: boolean
}

export function useGraphData(response: QueryResponse | null, baseGraph: ApiGraphData | null): GraphData {
  const nodeCacheRef = useRef<Map<string, D3Node>>(new Map())

  return useMemo(() => {
    const activeGraph = response?.graph || baseGraph
    if (!activeGraph) return { nodes: [], edges: [], loading: false }

    // Reuse existing node objects to preserve x/y/vx/vy positions
    const nextNodes: D3Node[] = activeGraph.nodes.map(n => {
      const cached = nodeCacheRef.current.get(n.id)
      if (cached) {
        // Update data but keep simulation properties
        return Object.assign(cached, n)
      }
      const newNode = { ...n } as D3Node
      nodeCacheRef.current.set(n.id, newNode)
      return newNode
    })

    // Clean up cache for nodes no longer present (optional, but good for long sessions)
    const nextIds = new Set(nextNodes.map(n => n.id))
    for (const id of nodeCacheRef.current.keys()) {
      if (!nextIds.has(id)) nodeCacheRef.current.delete(id)
    }

    const edges: D3Edge[] = activeGraph.edges.map(e => ({
      source: e.source,
      target: e.target,
      type: e.type,
    }))

    return { nodes: nextNodes, edges, loading: false }
  }, [response, baseGraph])
}
