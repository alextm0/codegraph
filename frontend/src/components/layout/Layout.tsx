import type { QueryResponse, GraphNode } from '../../types/api'
import { useResizablePanel } from '../../hooks/useResizablePanel'
import { useGraphData } from '../../hooks/useGraphData'
import { useFileTree } from '../../hooks/useFileTree'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useQuery } from '../../hooks/useQuery'
import ResizeHandle from './ResizeHandle'
import StatusBar from './StatusBar'
import ProjectTree from '../sidebar/ProjectTree'
import GraphCanvas from '../graph/GraphCanvas'
import RightPanel from '../panel/RightPanel'
import QueryInput from '../panel/QueryInput'
import SeedsList from '../panel/SeedsList'
import ResultsList from '../panel/ResultsList'
import ErrorBoundary from '../ErrorBoundary'

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
  selectedNode,
  focusPath,
  onFocusPath,
}: LayoutProps) {
  const { task, setTask, topK, setTopK, loading: queryLoading, error: queryError, runQuery } = useQuery(onQueryResult)
  const { width: sidebarWidth, handleMouseDown: handleLeftMouseDown } = useResizablePanel(280)
  const { width: rightPanelWidth, handleMouseDown: handleRightMouseDown } = useResizablePanel(380, 250, 600, 'left')
  const { nodes, edges, loading: graphLoading } = useGraphData(queryResult, focusPath)
  const wsState = useWebSocket()

  const seeds = queryResult?.seeds ?? []
  const pprResults = queryResult?.ppr_results ?? []
  const bm25Results = queryResult?.bm25_results ?? []

  const { tree, loading: treeLoading } = useFileTree(pprResults)

  return (
    <>
    <div
      style={{
        display: 'flex',
        height: 'calc(100vh - 24px)',
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
          overflow: 'hidden',
          borderRight: '1px solid var(--border)',
          minWidth: 200,
          maxWidth: 520,
        }}
      >
        {/* Query input — fixed at top */}
        <div style={{ flexShrink: 0, padding: 12, borderBottom: '1px solid var(--border)' }}>
          <QueryInput
            task={task}
            setTask={setTask}
            topK={topK}
            setTopK={setTopK}
            loading={queryLoading}
            error={queryError}
            onRun={runQuery}
          />
        </div>

        {/* Project tree — takes all remaining vertical space */}
        <div style={{ flex: 1, overflow: 'hidden', padding: '0 12px', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <ProjectTree
            tree={tree}
            onFocusPath={onFocusPath}
            currentFocus={focusPath}
            loading={treeLoading}
          />
        </div>

        {/* Seeds + Results — shown at bottom only when results exist */}
        {(seeds.length > 0 || pprResults.length > 0 || bm25Results.length > 0) && (
          <div style={{
            flexShrink: 0,
            maxHeight: '45vh',
            overflowY: 'auto',
            padding: '0 12px 12px',
            borderTop: '1px solid var(--border)',
          }}>
            <SeedsList seeds={seeds} />
            <ResultsList results={pprResults} bm25Results={bm25Results} />
          </div>
        )}
      </div>

      {/* Left Resize handle */}
      <ResizeHandle onMouseDown={handleLeftMouseDown} />

      {/* Graph area */}
      <div style={{ flex: 1, position: 'relative', display: 'flex' }}>
        <GraphCanvas
          nodes={nodes}
          edges={edges}
          onNodeSelect={onNodeSelect}
          selectedNode={selectedNode}
        />

        {/* Query loading overlay */}
        {queryLoading && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(15,17,23,0.65)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            zIndex: 20,
            backdropFilter: 'blur(2px)',
            pointerEvents: 'none',
          }}>
            <div style={{
              width: 32,
              height: 32,
              border: '3px solid var(--border)',
              borderTopColor: 'var(--accent)',
              borderRadius: '50%',
              animation: 'spin 0.75s linear infinite',
            }} />
            <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Running query…</div>
          </div>
        )}

        {/* Subgraph loading badge */}
        {graphLoading && !queryLoading && (
          <div style={{
            position: 'absolute',
            top: 12,
            right: 12,
            backgroundColor: 'rgba(0,0,0,0.6)',
            padding: '4px 12px',
            borderRadius: 16,
            fontSize: '0.8rem',
            color: 'var(--text-muted)',
          }}>
            Loading subgraph…
          </div>
        )}

        {/* Right Panel overlay */}
        {selectedNode && (
          <>
            <ResizeHandle onMouseDown={handleRightMouseDown} />
            <ErrorBoundary fallback={
              <div style={{
                width: rightPanelWidth,
                backgroundColor: 'var(--surface)',
                borderLeft: '1px solid var(--border)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                padding: 24,
                color: 'var(--red)',
                fontSize: 12,
              }}>
                <div style={{ fontWeight: 600 }}>Failed to load node detail</div>
                <button
                  onClick={() => onNodeSelect(null)}
                  style={{
                    padding: '4px 12px',
                    background: 'var(--surface2)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text)',
                    cursor: 'pointer',
                    fontFamily: 'var(--font)',
                    fontSize: 12,
                  }}
                >
                  Close
                </button>
              </div>
            }>
              <RightPanel
                selectedNode={selectedNode}
                onClose={() => onNodeSelect(null)}
                onNodeSelect={onNodeSelect}
                width={rightPanelWidth}
              />
            </ErrorBoundary>
          </>
        )}
      </div>
    </div>
    <StatusBar
      wsState={wsState}
      nodeCount={nodes.length}
      edgeCount={edges.length}
    />
    </>
  )
}
