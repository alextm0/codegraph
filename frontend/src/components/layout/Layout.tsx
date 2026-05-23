import type { QueryResponse, GraphNode } from '../../types/api'
import { useResizablePanel } from '../../hooks/useResizablePanel'
import { useGraphData } from '../../hooks/useGraphData'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useQuery } from '../../hooks/useQuery'
import TopBar from './TopBar'
import StatusBar from './StatusBar'
import GraphCanvas from '../graph/GraphCanvas'
import RightPanel from '../panel/RightPanel'
import ResultsList from '../panel/ResultsList'
import LeftRail from './LeftRail'
import ErrorBoundary from '../ErrorBoundary'

interface LayoutProps {
  queryResult: QueryResponse | null
  selectedNode: GraphNode | null
  onQueryResult: (result: QueryResponse) => void
  onNodeSelect: (node: GraphNode | null) => void
}

export default function Layout({
  queryResult,
  onQueryResult,
  onNodeSelect,
  selectedNode,
}: LayoutProps) {
  const {
    task, setTask, topK, setTopK,
    loading: queryLoading, error: queryError, runQuery,
  } = useQuery(onQueryResult)

  const { width: rightPanelWidth, handleMouseDown: handleRightMouseDown } =
    useResizablePanel(380, 250, 600, 'left')

  const { nodes, edges, loading: graphLoading } = useGraphData(queryResult)
  const wsState = useWebSocket()

  const seeds       = queryResult?.seeds ?? []
  const pprResults  = queryResult?.ppr_results ?? []
  const hasResults  = pprResults.length > 0

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '320px 1fr',
        gridTemplateRows: 'var(--topbar-h) 1fr var(--statusbar-h)',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: 'var(--bg)',
      }}
    >
      <TopBar
        nodeCount={nodes.length}
        edgeCount={edges.length}
        wsConnected={wsState.connected}
        topK={topK}
      />

      {/* Left Rail */}
      <div style={{ gridRow: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <LeftRail
          task={task}
          setTask={setTask}
          topK={topK}
          setTopK={setTopK}
          loading={queryLoading}
          error={queryError}
          onRun={runQuery}
          seeds={seeds}
          nodes={nodes}
          hasRun={hasResults || seeds.length > 0}
          onNodeSelect={onNodeSelect}
        />
      </div>

      {/* Center + Right — flex row */}
      <div style={{ gridRow: 2, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* Graph canvas */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex' }}>
          <GraphCanvas
            nodes={nodes}
            edges={edges}
            onNodeSelect={onNodeSelect}
            selectedNode={selectedNode}
            dampingFactor={queryResult?.damping_factor}
            topK={queryResult?.top_k}
          />

          {/* Loading overlay */}
          {queryLoading && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background: 'color-mix(in oklch, var(--bg) 78%, transparent)',
                backdropFilter: 'blur(2px)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 12,
                zIndex: 20,
                pointerEvents: 'none',
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  border: '1.5px solid var(--border)',
                  borderTopColor: 'var(--accent)',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                }}
              />
              <div
                style={{
                  fontSize: 9.5,
                  color: 'var(--accent)',
                  letterSpacing: '0.20em',
                  textTransform: 'uppercase',
                }}
              >
                ppr.iterating · α={queryResult?.damping_factor?.toFixed(2) ?? '0.70'} · ε=1e−7
              </div>
            </div>
          )}

          {graphLoading && !queryLoading && (
            <div
              style={{
                position: 'absolute',
                top: 8,
                right: 8,
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                padding: '3px 10px',
                fontSize: 9,
                letterSpacing: '0.12em',
                color: 'var(--text-muted)',
              }}
            >
              graph.syncing…
            </div>
          )}
        </div>

        {/* Right pane — node detail or results list */}
        {selectedNode ? (
          <>
            <ResizeDivider onMouseDown={handleRightMouseDown} />
            <ErrorBoundary fallback={<RightPanelError onClose={() => onNodeSelect(null)} />}>
              <RightPanel
                selectedNode={selectedNode}
                onClose={() => onNodeSelect(null)}
                onNodeSelect={onNodeSelect}
                width={rightPanelWidth}
              />
            </ErrorBoundary>
          </>
        ) : hasResults ? (
          <div style={{ width: 380, flexShrink: 0 }}>
            <ResultsList results={pprResults} onNodeSelect={onNodeSelect} />
          </div>
        ) : null}
      </div>

      <StatusBar
        wsState={wsState}
        nodeCount={nodes.length}
        edgeCount={edges.length}
      />
    </div>
  )
}

function ResizeDivider({ onMouseDown }: { onMouseDown: (e: React.MouseEvent) => void }) {
  return (
    <div
      onMouseDown={onMouseDown}
      style={{
        width: 4,
        cursor: 'col-resize',
        background: 'transparent',
        flexShrink: 0,
        transition: 'background 120ms',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'var(--accent)' }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
    />
  )
}

function RightPanelError({ onClose }: { onClose: () => void }) {
  return (
    <div
      style={{
        width: 380,
        background: 'var(--surface)',
        borderLeft: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        padding: 24,
        color: 'oklch(0.70 0.15 25)',
        fontSize: 11,
        fontFamily: 'var(--font-mono)',
        letterSpacing: '0.06em',
      }}
    >
      <div>// node.detail failed to load</div>
      <button
        onClick={onClose}
        style={{
          padding: '4px 14px',
          background: 'var(--surface2)',
          border: '1px solid var(--border)',
          color: 'var(--text)',
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '0.10em',
        }}
      >
        [close]
      </button>
    </div>
  )
}
