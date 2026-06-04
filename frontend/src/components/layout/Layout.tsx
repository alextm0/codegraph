import { useCallback, useRef, useEffect, useMemo } from 'react'
import type { QueryResponse, GraphNode, GraphData } from '../../types/api'
import { ProjectHistoryItem, type GraphStats } from '../../api/client'
import { useResizablePanel } from '../../hooks/useResizablePanel'
import { useGraphData } from '../../hooks/useGraphData'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useQuery } from '../../hooks/useQuery'
import { useCollapsedRail } from '../../hooks/useCollapsedRail'
import TopBar from './TopBar'
import StatusBar from './StatusBar'
import GraphCanvas from '../graph/GraphCanvas'
import LeftRail from './LeftRail'
import CollapsedRailHandle from './CollapsedRailHandle'
import RightPanelTabs, { useRightPanelTabs } from '../panel/RightPanelTabs'
import ViewModeBanner from './ViewModeBanner'
import ClearSelectionPill from '../graph/ClearSelectionPill'

const EMPTY_PATH_HIGHLIGHT: string[] = []

interface LayoutProps {
  queryResult: QueryResponse | null
  baseGraph: GraphData | null
  focusGraph: GraphData | null
  onFocusGraph: (graph: GraphData | null) => void
  selectedNode: GraphNode | null
  selectedFilePath: string | null
  onSelectedFilePath: (path: string | null) => void
  gitInfo?: { repo: string; commit: string }
  projectHistory?: ProjectHistoryItem[]
  onQueryResult: (result: QueryResponse) => void
  onNodeSelect: (node: GraphNode | null) => void
  onResetGraph: () => void
  graphRevision: number
  fitViewKey: number
  fileFocusKey: number
  onGraphRefresh?: () => void
  graphStats?: GraphStats
}

export default function Layout({
  queryResult,
  baseGraph,
  focusGraph,
  onFocusGraph,
  onQueryResult,
  onNodeSelect,
  selectedNode,
  selectedFilePath,
  onSelectedFilePath,
  gitInfo,
  projectHistory = [],
  onGraphRefresh,
  onResetGraph,
  graphRevision,
  fitViewKey,
  fileFocusKey,
  graphStats,
}: LayoutProps) {
  const { activeTab, setActiveTab, onQueryComplete, onNodeSelected, onFileSelected } =
    useRightPanelTabs()
  const { collapsed, toggle: toggleRail, setCollapsed } = useCollapsedRail()

  const handleQueryResult = useCallback(
    (result: QueryResponse) => {
      onQueryComplete()
      onQueryResult(result)
    },
    [onQueryResult, onQueryComplete],
  )

  const {
    task, setTask, topK, setTopK, options, setOptions,
    loading: queryLoading, error: queryError, runQuery, resetQuery,
  } = useQuery(handleQueryResult)

  const { width: rightPanelWidth, handleMouseDown: handleRightMouseDown } =
    useResizablePanel(380, 250, 600, 'left')

  const { nodes, edges, loading: graphLoading, isDatabaseEmpty, viewMode } = useGraphData(
    queryResult, baseGraph, focusGraph, graphRevision,
  )
  const wsState = useWebSocket()
  const { lastMessage } = wsState
  const fileChangeTimer = useRef<number>()

  const rebuildActive =
    lastMessage?.type === 'rebuild_started' || lastMessage?.type === 'rebuild_progress'

  useEffect(() => {
    if (lastMessage?.type === 'rebuild_complete' && onGraphRefresh) {
      onGraphRefresh()
      onFocusGraph(null)
    }
  }, [lastMessage, onGraphRefresh, onFocusGraph])

  useEffect(() => {
    if (lastMessage?.type === 'file_changed' && onGraphRefresh) {
      window.clearTimeout(fileChangeTimer.current)
      fileChangeTimer.current = window.setTimeout(() => onGraphRefresh(), 800)
    }
    return () => window.clearTimeout(fileChangeTimer.current)
  }, [lastMessage, onGraphRefresh])

  const seeds = queryResult?.seeds ?? []
  const pprResults = queryResult?.ppr_results ?? []
  const bm25Results = queryResult?.bm25_results ?? []
  const hasResults = pprResults.length > 0 || bm25Results.length > 0

  const treeNodes = baseGraph?.nodes ?? nodes

  const handleNodeSelect = useCallback(
    (node: GraphNode | null) => {
      if (node) onNodeSelected()
      onNodeSelect(node)
    },
    [onNodeSelect, onNodeSelected],
  )

  const handleFileSelect = useCallback(
    (filePath: string) => {
      onSelectedFilePath(filePath)
      onFileSelected()
      onNodeSelect(null)
    },
    [onSelectedFilePath, onFileSelected, onNodeSelect],
  )

  const effectiveFileFocusKey = selectedNode ? 0 : fileFocusKey

  const showRightPanel = hasResults || selectedNode || selectedFilePath

  const handleRestoreFullGraph = useCallback(() => {
    resetQuery()
    onResetGraph()
    onSelectedFilePath(null)
    setActiveTab('results')
  }, [resetQuery, onResetGraph, onSelectedFilePath, setActiveTab])

  const handleClearAll = useCallback(() => {
    onNodeSelect(null)
    onSelectedFilePath(null)
  }, [onNodeSelect, onSelectedFilePath])

  /** Esc: clear selection first, then exit query / file-focus back to the full graph. */
  const handleEscape = useCallback(() => {
    if (selectedNode || selectedFilePath) {
      handleClearAll()
      return
    }
    if (viewMode !== 'full') {
      handleRestoreFullGraph()
    }
  }, [
    selectedNode,
    selectedFilePath,
    viewMode,
    handleClearAll,
    handleRestoreFullGraph,
  ])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleEscape()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handleEscape])

  const pathHighlightIds = useMemo(() => {
    const path = selectedNode?.reasoning_path
    return path && path.length > 1 ? path : EMPTY_PATH_HIGHLIGHT
  }, [selectedNode])

  const showClearPill = Boolean(selectedNode || selectedFilePath)

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: collapsed ? '1fr' : 'var(--rail-w) 1fr',
        gridTemplateRows: 'var(--topbar-h) 1fr var(--statusbar-h)',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: 'var(--bg)',
        transition: 'grid-template-columns var(--dur-slow) var(--ease)',
      }}
    >
      <TopBar gitInfo={gitInfo} projectHistory={projectHistory} onGraphRefresh={onGraphRefresh} />

      <div
        style={{
          gridColumn: 1,
          gridRow: 2,
          overflow: 'hidden',
          display: collapsed ? 'none' : 'flex',
          flexDirection: 'column',
          minWidth: 0,
        }}
      >
        <LeftRail
          task={task}
          setTask={setTask}
          topK={topK}
          setTopK={setTopK}
          options={options}
          setOptions={setOptions}
          loading={queryLoading}
          error={queryError}
          onRun={runQuery}
          seeds={seeds}
          nodes={nodes}
          treeNodes={treeNodes}
          hasRun={hasResults || seeds.length > 0}
          selectedFilePath={selectedFilePath}
          onFileSelect={handleFileSelect}
          onNodeSelect={n => handleNodeSelect(n)}
          onCollapse={toggleRail}
        />
      </div>

      <div
        style={{
          gridColumn: collapsed ? 1 : 2,
          gridRow: 2,
          display: 'flex',
          overflow: 'hidden',
          position: 'relative',
          minWidth: 0,
        }}
      >
        {collapsed && <CollapsedRailHandle onOpen={() => setCollapsed(false)} />}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', minWidth: 0 }}>
          <GraphCanvas
            key={graphRevision}
            nodes={nodes}
            edges={edges}
            onNodeSelect={handleNodeSelect}
            selectedNode={selectedNode}
            highlightFilePath={selectedFilePath}
            pathHighlightIds={pathHighlightIds}
            viewMode={viewMode}
            dampingFactor={queryResult?.damping_factor}
            topK={queryResult?.top_k}
            showPprReadout={viewMode === 'query'}
            fitViewKey={fitViewKey}
            fileFocusKey={effectiveFileFocusKey}
            projectHistory={projectHistory}
            isDatabaseEmpty={isDatabaseEmpty}
            rebuildActive={rebuildActive}
            rebuildMessage={lastMessage}
          />

          <ClearSelectionPill
            visible={showClearPill}
            onClear={handleEscape}
          />

          {viewMode === 'focus' && (
            <ViewModeBanner nodeCount={nodes.length} />
          )}

          {queryLoading && (
            <div style={{ position: 'absolute', inset: 0, background: 'color-mix(in oklch, var(--bg) 78%, transparent)', backdropFilter: 'blur(2px)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, zIndex: 20, pointerEvents: 'none' }}>
              <div style={{ width: 32, height: 32, border: '1.5px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              <div style={{ fontSize: 10, color: 'var(--accent)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                Running PPR · α={queryResult?.damping_factor?.toFixed(2) ?? '0.70'}
              </div>
            </div>
          )}

          {graphLoading && !queryLoading && (
            <div className="surface-elevated" style={{ position: 'absolute', top: 12, right: 12, padding: '6px 12px', fontSize: 11, color: 'var(--text-muted)' }}>
              Syncing graph…
            </div>
          )}
        </div>

        {showRightPanel && (
          <>
            <ResizeDivider onMouseDown={handleRightMouseDown} />
            <RightPanelTabs
              activeTab={activeTab}
              onTabChange={setActiveTab}
              queryResult={queryResult}
              task={task}
              selectedNode={selectedNode}
              selectedFilePath={selectedFilePath}
              graphNodes={treeNodes}
              onNodeSelect={handleNodeSelect}
              onFileClose={() => onSelectedFilePath(null)}
              width={rightPanelWidth}
              seeds={seeds}
              hasResults={hasResults}
            />
          </>
        )}
      </div>

      <StatusBar
        wsState={wsState}
        nodeCount={nodes.length}
        edgeCount={edges.length}
        graphStats={graphStats}
        graphViewMode={viewMode}
      />
    </div>
  )
}

function ResizeDivider({ onMouseDown }: { onMouseDown: (e: React.MouseEvent) => void }) {
  return (
    <div
      onMouseDown={onMouseDown}
      style={{ width: 4, cursor: 'col-resize', background: 'transparent', flexShrink: 0 }}
      onMouseEnter={e => { e.currentTarget.style.background = 'var(--accent)' }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
    />
  )
}
