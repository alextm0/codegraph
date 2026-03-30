import { useState, useCallback } from 'react'
import Layout from './components/layout/Layout'
import { QueryResponse, GraphNode } from './types/api'

export default function App() {
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [focusPath, setFocusPath] = useState<string | null>(null)

  const handleQueryResult = useCallback((result: QueryResponse) => {
    setQueryResult(result)
    setSelectedNode(null)
  }, [])

  return (
    <Layout
      queryResult={queryResult}
      selectedNode={selectedNode}
      focusPath={focusPath}
      onQueryResult={handleQueryResult}
      onNodeSelect={setSelectedNode}
      onFocusPath={setFocusPath}
    />
  )
}
