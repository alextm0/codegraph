import { useState, useEffect, useMemo } from 'react'
import { getSubgraph } from '../api/client'
import type { QueryResponse, GraphData as APIGraphData } from '../types/api'
import type { D3Node, D3Edge } from '../types/graph'

interface GraphData {
  nodes: D3Node[]
  edges: D3Edge[]
  loading: boolean
}

export function useGraphData(response: QueryResponse | null, focusPath: string | null = null): GraphData {
  const [subgraph, setSubgraph] = useState<APIGraphData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (focusPath) {
      setLoading(true)
      getSubgraph(focusPath)
        .then(res => setSubgraph(res.graph))
        .catch(err => console.error('Failed to fetch subgraph', err))
        .finally(() => setLoading(false))
    } else {
      setSubgraph(null)
    }
  }, [focusPath])

  const graphToUse = focusPath ? subgraph : response?.graph

  return useMemo(() => {
    if (!graphToUse) return { nodes: [], edges: [], loading }

    const nodes: D3Node[] = graphToUse.nodes.map((n) => ({ ...n }))
    const edges: D3Edge[] = graphToUse.edges.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type,
    }))

    return { nodes, edges, loading }
  }, [graphToUse, loading])
}
