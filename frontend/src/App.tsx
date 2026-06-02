import { useState, useCallback, useEffect } from 'react'
import { ThemeProvider } from './context/ThemeContext'
import Layout from './components/layout/Layout'
import { getHealth, getBaseGraph, getStats, ProjectHistoryItem, type GraphStats } from './api/client'
import type { QueryResponse, GraphNode, GraphData } from './types/api'

export default function App() {
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [gitInfo, setGitInfo] = useState<{ repo: string; commit: string } | undefined>()
  const [baseGraph, setBaseGraph] = useState<GraphData | null>(null)
  const [projectHistory, setProjectHistory] = useState<ProjectHistoryItem[]>([])
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null)
  const [focusGraph, setFocusGraph] = useState<GraphData | null>(null)

  const refreshGraph = useCallback(() => {
    getBaseGraph().then(setBaseGraph).catch(err => console.error('Failed to fetch base graph', err))
    getStats().then(setGraphStats).catch(err => console.error('Failed to fetch stats', err))
    getHealth().then(res => {
      if (res.git_info) setGitInfo(res.git_info)
      if (res.project_history) setProjectHistory(res.project_history)
    }).catch(err => console.error('Failed to fetch health', err))
  }, [])

  useEffect(() => {
    refreshGraph()
  }, [refreshGraph])

  const handleQueryResult = useCallback((result: QueryResponse) => {
    setQueryResult(result)
    setFocusGraph(null)
    setSelectedNode(null)
    if (result.git_info) setGitInfo(result.git_info)
  }, [])

  return (
    <ThemeProvider>
      <Layout
        queryResult={queryResult}
        baseGraph={baseGraph}
        focusGraph={focusGraph}
        onFocusGraph={setFocusGraph}
        selectedNode={selectedNode}
        gitInfo={gitInfo}
        projectHistory={projectHistory}
        onQueryResult={handleQueryResult}
        onNodeSelect={setSelectedNode}
        onGraphRefresh={refreshGraph}
        graphStats={graphStats ?? undefined}
      />
    </ThemeProvider>
  )
}
