import { useState, useCallback, useEffect } from 'react'
import { ThemeProvider } from './context/ThemeContext'
import Layout from './components/layout/Layout'
import { getHealth, getBaseGraph, ProjectHistoryItem } from './api/client'
import type { QueryResponse, GraphNode, GraphData } from './types/api'

export default function App() {
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [gitInfo, setGitInfo] = useState<{ repo: string; commit: string } | undefined>()
  const [baseGraph, setBaseGraph] = useState<GraphData | null>(null)
  const [projectHistory, setProjectHistory] = useState<ProjectHistoryItem[]>([])

  useEffect(() => {
    getHealth().then(res => {
      if (res.git_info) setGitInfo(res.git_info)
      if (res.project_history) setProjectHistory(res.project_history)
    }).catch(err => console.error('Failed to fetch git info', err))

    getBaseGraph().then(res => {
      setBaseGraph(res)
    }).catch(err => console.error('Failed to fetch base graph', err))
  }, [])

  const handleQueryResult = useCallback((result: QueryResponse) => {
    setQueryResult(result)
    setSelectedNode(null)
    if (result.git_info) setGitInfo(result.git_info)
  }, [])

  return (
    <ThemeProvider>
      <Layout
        queryResult={queryResult}
        baseGraph={baseGraph}
        selectedNode={selectedNode}
        gitInfo={gitInfo}
        projectHistory={projectHistory}
        onQueryResult={handleQueryResult}
        onNodeSelect={setSelectedNode}
      />
    </ThemeProvider>
  )
}
