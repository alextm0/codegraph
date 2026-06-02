import { useState, useCallback } from 'react'
import type { GraphNode, QueryResponse } from '../../types/api'
import type { SeedInfo } from '../../types/api'
import LatticeButton from '../ui/LatticeButton'
import ResultsList from './ResultsList'
import ExplainPanel from './ExplainPanel'
import RightPanel from './RightPanel'
import FilePanel from './FilePanel'
import ErrorBoundary from '../ErrorBoundary'

export type RightTab = 'results' | 'explain' | 'inspector' | 'file'

interface RightPanelTabsProps {
  activeTab: RightTab
  onTabChange: (tab: RightTab) => void
  queryResult: QueryResponse | null
  task: string
  selectedNode: GraphNode | null
  selectedFilePath: string | null
  graphNodes: GraphNode[]
  onNodeSelect: (node: GraphNode | null) => void
  onFileClose: () => void
  width: number
  seeds: SeedInfo[]
  hasResults: boolean
}

export default function RightPanelTabs({
  activeTab,
  onTabChange,
  queryResult,
  task,
  selectedNode,
  selectedFilePath,
  graphNodes,
  onNodeSelect,
  onFileClose,
  width,
  seeds,
  hasResults,
}: RightPanelTabsProps) {
  const showPanel = hasResults || selectedNode || selectedFilePath

  if (!showPanel) return null

  // The Code tab follows the explicitly-selected file, or falls back to the
  // file that owns the currently-selected node, so it works for any node.
  const codeFilePath = selectedFilePath ?? selectedNode?.file_path ?? null

  const tabs: { id: RightTab; label: string; disabled?: boolean }[] = [
    { id: 'file', label: 'Code', disabled: !codeFilePath },
    { id: 'inspector', label: 'Inspector' },
    { id: 'results', label: 'Results', disabled: !hasResults },
    { id: 'explain', label: 'Explain', disabled: !hasResults },
  ]

  return (
    <div
      style={{
        width,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--surface)',
        borderLeft: '1px solid var(--border)',
      }}
    >
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface2)',
          flexShrink: 0,
          gap: 2,
          padding: '4px 6px',
        }}
      >
        {tabs.map(tab => (
          <LatticeButton
            key={tab.id}
            variant="secondary"
            active={activeTab === tab.id}
            onClick={() => onTabChange(tab.id)}
            disabled={tab.disabled}
            style={{
              flex: 1,
              padding: '6px 4px',
              fontSize: 11,
              opacity: tab.disabled ? 0.35 : 1,
            }}
          >
            {tab.label}
          </LatticeButton>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        {activeTab === 'file' && codeFilePath && (
          <FilePanel
            filePath={codeFilePath}
            activeNode={selectedNode}
            graphNodes={graphNodes}
            onNodeSelect={n => onNodeSelect(n)}
            onClose={() => {
              if (selectedFilePath) onFileClose()
              else onTabChange('inspector')
            }}
          />
        )}
        {activeTab === 'results' && queryResult && (
          <ResultsList
            results={queryResult.ppr_results}
            bm25Results={queryResult.bm25_results}
            task={task}
            onNodeSelect={onNodeSelect}
          />
        )}
        {activeTab === 'explain' && queryResult && (
          <ExplainPanel
            results={queryResult.ppr_results}
            seeds={queryResult.seeds}
            onNodeSelect={onNodeSelect}
          />
        )}
        {activeTab === 'inspector' && (
          selectedNode ? (
            <ErrorBoundary>
              <RightPanel
                selectedNode={selectedNode}
                onClose={() => onNodeSelect(null)}
                onNodeSelect={onNodeSelect}
                width={width}
                seeds={seeds}
                embedded
              />
            </ErrorBoundary>
          ) : (
            <div style={{ padding: 16, fontSize: 12, color: 'var(--text-muted)' }}>
              Select a node on the graph or from the file tree.
            </div>
          )
        )}
      </div>
    </div>
  )
}

/** Hook to manage tab state with auto-switching on query/node/file select. */
export function useRightPanelTabs() {
  const [activeTab, setActiveTab] = useState<RightTab>('results')

  const onQueryComplete = useCallback(() => setActiveTab('results'), [])
  const onNodeSelected = useCallback(() => setActiveTab('inspector'), [])
  const onFileSelected = useCallback(() => setActiveTab('file'), [])

  return { activeTab, setActiveTab, onQueryComplete, onNodeSelected, onFileSelected }
}
