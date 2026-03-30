import type { QueryResponse, GraphNode } from '../../types/api'
import { useResizablePanel } from '../../hooks/useResizablePanel'
import { useGraphData } from '../../hooks/useGraphData'
import ResizeHandle from './ResizeHandle'
import GraphCanvas from '../graph/GraphCanvas'
import QueryInput from '../panel/QueryInput'
import SeedsList from '../panel/SeedsList'
import ResultsList from '../panel/ResultsList'

interface LayoutProps {
  queryResult: QueryResponse | null
  selectedNode: GraphNode | null
  focusPath: string | null
  onQueryResult: (result: QueryResponse) => void
  onNodeSelect: (node: GraphNode | null) => void
  onFocusPath: (path: string | null) => void
}

export default function Layout({
  queryResult,
  onQueryResult,
  onNodeSelect,
}: LayoutProps) {
  const { width: sidebarWidth, handleMouseDown } = useResizablePanel(280)
  const { nodes, edges } = useGraphData(queryResult)

  const seeds = queryResult?.seeds ?? []
  const pprResults = queryResult?.ppr_results ?? []
  const bm25Results = queryResult?.bm25_results ?? []

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        overflow: 'hidden',
        userSelect: 'none',
      }}
    >
      {/* Left sidebar */}
      <div
        style={{
          width: sidebarWidth,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          padding: 12,
          overflowY: 'auto',
          overflowX: 'hidden',
          borderRight: '1px solid var(--border)',
          minWidth: 200,
          maxWidth: 520,
        }}
      >
        <QueryInput onResult={onQueryResult} />
        <SeedsList seeds={seeds} />
        <ResultsList results={pprResults} bm25Results={bm25Results} />
      </div>

      {/* Resize handle */}
      <ResizeHandle onMouseDown={handleMouseDown} />

      {/* Graph area */}
      <GraphCanvas
        nodes={nodes}
        edges={edges}
        onNodeSelect={onNodeSelect}
      />
    </div>
  )
}
