import { useMemo } from 'react'
import type { QueryResponse } from '../types/api'
import type { D3Node, D3Edge } from '../types/graph'

interface GraphData {
  nodes: D3Node[]
  edges: D3Edge[]
}

export function useGraphData(response: QueryResponse | null): GraphData {
  return useMemo(() => {
    if (!response?.graph) return { nodes: [], edges: [] }

    const nodes: D3Node[] = response.graph.nodes.map((n) => ({ ...n }))

    const edges: D3Edge[] = response.graph.edges.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type,
    }))

    return { nodes, edges }
  }, [response])
}
