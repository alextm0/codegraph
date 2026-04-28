import { useState, useCallback } from 'react'
import { ThemeProvider } from './context/ThemeContext'
import Layout from './components/layout/Layout'
import type { QueryResponse, GraphNode } from './types/api'

export default function App() {
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  const handleQueryResult = useCallback((result: QueryResponse) => {
    setQueryResult(result)
    setSelectedNode(null)
  }, [])

  return (
    <ThemeProvider>
      <Layout
        queryResult={queryResult}
        selectedNode={selectedNode}
        onQueryResult={handleQueryResult}
        onNodeSelect={setSelectedNode}
      />
    </ThemeProvider>
  )
}
