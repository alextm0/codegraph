import { useState, useCallback, useEffect } from 'react'
import { ThemeProvider } from './context/ThemeContext'
import Layout from './components/layout/Layout'
import { getHealth, getBaseGraph, getStats, ProjectHistoryItem, type GraphStats } from './api/client'
import type { QueryResponse, GraphNode, GraphData } from './types/api'

export default function App() {
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null)
  const [gitInfo, setGitInfo] = useState<{ repo: string; commit: string } | undefined>()
  const [baseGraph, setBaseGraph] = useState<GraphData | null>(null)
  const [projectHistory, setProjectHistory] = useState<ProjectHistoryItem[]>([])
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null)
  const [focusGraph, setFocusGraph] = useState<GraphData | null>(null)
  const [graphRevision, setGraphRevision] = useState(0)
  const [fitViewKey, setFitViewKey] = useState(0)
  const [fileFocusKey, setFileFocusKey] = useState(0)

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

  const handleFileSelect = useCallback((filePath: string | null) => {
    setSelectedFilePath(filePath)
    if (filePath) setFileFocusKey(k => k + 1)
  }, [])

  const handleQueryResult = useCallback((result: QueryResponse) => {
    setQueryResult(result)
    setFocusGraph(null)
    setSelectedNode(null)
    setSelectedFilePath(null)
    if (result.git_info) setGitInfo(result.git_info)
  }, [])

  const handleResetGraph = useCallback(() => {
    setQueryResult(null)
    setFocusGraph(null)
    setSelectedNode(null)
    setSelectedFilePath(null)
    setGraphRevision(r => r + 1)
    setFitViewKey(k => k + 1)
  }, [])

  return (
    <ThemeProvider>
      <Layout
        queryResult={queryResult}
        baseGraph={baseGraph}
        focusGraph={focusGraph}
        onFocusGraph={setFocusGraph}
        selectedNode={selectedNode}
        selectedFilePath={selectedFilePath}
        onSelectedFilePath={handleFileSelect}
        gitInfo={gitInfo}
        projectHistory={projectHistory}
        onQueryResult={handleQueryResult}
        onNodeSelect={setSelectedNode}
        onResetGraph={handleResetGraph}
        graphRevision={graphRevision}
        fitViewKey={fitViewKey}
        fileFocusKey={fileFocusKey}
        onGraphRefresh={refreshGraph}
        graphStats={graphStats ?? undefined}
      />
    </ThemeProvider>
  )
}
