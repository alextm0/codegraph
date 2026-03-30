import { useState, useCallback } from 'react'
import type { GraphNode } from '../types/api'

interface UseNodeSelectionReturn {
  selectedNode: GraphNode | null
  selectNode: (node: GraphNode | null) => void
  clearSelection: () => void
}

export function useNodeSelection(): UseNodeSelectionReturn {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  const selectNode = useCallback((node: GraphNode | null) => {
    setSelectedNode(node)
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedNode(null)
  }, [])

  return { selectedNode, selectNode, clearSelection }
}
