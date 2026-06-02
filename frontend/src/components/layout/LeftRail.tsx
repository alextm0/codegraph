import { useState, type ReactNode } from 'react'
import type { SeedInfo, GraphNode } from '../../types/api'
import type { QueryOptions } from '../../hooks/useQuery'
import LatticeButton from '../ui/LatticeButton'
import LatticeTextarea from '../ui/LatticeTextarea'
import RangeField from '../ui/RangeField'
import ProjectTree from './ProjectTree'
import IconButton from '../ui/IconButton'

type RailTab = 'files' | 'query'

interface LeftRailProps {
  task: string
  setTask: (t: string) => void
  topK: number
  setTopK: (k: number) => void
  options: QueryOptions
  setOptions: (opts: QueryOptions) => void
  loading: boolean
  error: string | null
  onRun: () => void
  seeds: SeedInfo[]
  nodes: GraphNode[]
  treeNodes: GraphNode[]
  hasRun: boolean
  selectedFilePath: string | null
  onFileSelect: (filePath: string) => void
  onNodeSelect?: (node: GraphNode) => void
  onCollapse: () => void
}

export default function LeftRail(props: LeftRailProps) {
  const {
    task, setTask, topK, setTopK, options, setOptions,
    loading, error, onRun, seeds, nodes, treeNodes, hasRun,
    selectedFilePath, onFileSelect, onNodeSelect, onCollapse,
  } = props

  const [tab, setTab] = useState<RailTab>('files')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const totalW = seeds.reduce((a, s) => a + s.weight, 0)
  const maxWeight = seeds.length > 0 ? Math.max(...seeds.map(s => s.weight)) : 1

  return (
    <aside
      style={{
        borderRight: '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        height: '100%',
        width: '100%',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', gap: 4, flex: 1 }}>
          <TabButton active={tab === 'files'} onClick={() => setTab('files')}>
            Files
          </TabButton>
          <TabButton active={tab === 'query'} onClick={() => setTab('query')}>
            Query
            {hasRun && (
              <span
                style={{
                  marginLeft: 6,
                  fontSize: 9,
                  padding: '1px 5px',
                  borderRadius: 999,
                  background: 'var(--accent-soft)',
                  color: 'var(--accent)',
                }}
              >
                {seeds.length}
              </span>
            )}
          </TabButton>
        </div>
        <IconButton onClick={onCollapse} title="Collapse sidebar" style={{ fontSize: 16 }}>
          ‹
        </IconButton>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tab === 'files' && (
          <ProjectTree
            nodes={treeNodes}
            selectedFilePath={selectedFilePath}
            onFileSelect={onFileSelect}
          />
        )}

        {tab === 'query' && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            <div style={{ padding: 14, flexShrink: 0, borderBottom: '1px solid var(--border)' }}>
              <LatticeTextarea
                value={task}
                onChange={e => setTask(e.target.value)}
                onKeyDown={e => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    e.preventDefault()
                    if (task.trim()) onRun()
                  }
                }}
                rows={3}
                placeholder="Describe what to find…"
                style={{ userSelect: 'text' }}
              />

              {error && <ErrorBanner message={error} />}

              <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setShowAdvanced(v => !v)}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    fontSize: 11,
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontFamily: 'var(--font-body)',
                  }}
                >
                  {showAdvanced ? '▾' : '▸'} Advanced options
                </button>

                {showAdvanced && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <RangeField
                      label="Results (top_k)"
                      value={topK}
                      min={5}
                      max={30}
                      step={1}
                      onChange={setTopK}
                    />
                    <RangeField
                      label="Token budget"
                      value={options.tokenBudget}
                      min={1000}
                      max={12000}
                      step={500}
                      onChange={v => setOptions({ ...options, tokenBudget: v })}
                      formatValue={v => v.toLocaleString()}
                    />
                  </div>
                )}

                <LatticeButton
                  variant="primary"
                  onClick={onRun}
                  disabled={loading || !task.trim()}
                  style={{ width: '100%', padding: '10px 14px', fontSize: 13 }}
                >
                  {loading ? 'Running PPR…' : 'Run query'}
                </LatticeButton>

                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  <kbd style={kbdStyle}>⌘↵</kbd> to run
                </div>
              </div>
            </div>

            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div
                style={{
                  padding: '10px 14px',
                  borderBottom: '1px solid var(--border)',
                  background: 'var(--surface2)',
                  flexShrink: 0,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-dim)' }}>Seeds</span>
                {hasRun && (
                  <span className="font-mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    n={seeds.length} · Σ={totalW.toFixed(2)}
                  </span>
                )}
              </div>
              <SeedList
                seeds={seeds}
                nodes={nodes}
                hasRun={hasRun}
                maxWeight={maxWeight}
                onNodeSelect={onNodeSelect}
              />
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        flex: 1,
        padding: '8px 12px',
        fontSize: 12,
        fontWeight: active ? 600 : 500,
        color: active ? 'var(--text)' : 'var(--text-muted)',
        background: active ? 'var(--bg)' : 'transparent',
        border: active ? '1px solid var(--border)' : '1px solid transparent',
        borderRadius: 'var(--radius-sm)',
        cursor: 'pointer',
        fontFamily: 'var(--font-body)',
        transition: 'background var(--dur-fast), color var(--dur-fast)',
      }}
    >
      {children}
    </button>
  )
}

const kbdStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '2px 6px',
  marginRight: 4,
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)',
  background: 'var(--surface2)',
  fontSize: 10,
  fontFamily: 'var(--font-mono)',
  color: 'var(--text-dim)',
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      style={{
        marginTop: 10,
        padding: '10px 12px',
        background: 'color-mix(in oklch, var(--danger) 12%, transparent)',
        border: '1px solid color-mix(in oklch, var(--danger) 45%, var(--border))',
        borderRadius: 'var(--radius-sm)',
        fontSize: 12,
        color: 'var(--danger)',
        lineHeight: 1.45,
      }}
    >
      {message}
    </div>
  )
}

function SeedList({
  seeds, nodes, hasRun, maxWeight, onNodeSelect,
}: {
  seeds: SeedInfo[]
  nodes: GraphNode[]
  hasRun: boolean
  maxWeight: number
  onNodeSelect?: (node: GraphNode) => void
}) {
  return (
    <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
      {!hasRun ? (
        <EmptyHint>Run a query to see PPR seed entities and their weights.</EmptyHint>
      ) : seeds.length === 0 ? (
        <EmptyHint>No seeds matched — try a more specific task description.</EmptyHint>
      ) : (
        seeds.map((seed, i) => (
          <SeedRow
            key={`${seed.id}-${i}`}
            seed={seed}
            idx={i}
            max={maxWeight}
            nodes={nodes}
            onNodeSelect={onNodeSelect}
          />
        ))
      )}
    </div>
  )
}

function EmptyHint({ children }: { children: ReactNode }) {
  return (
    <div style={{ padding: 20, fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.55 }}>
      {children}
    </div>
  )
}

function SeedRow({
  seed, idx, max, nodes, onNodeSelect,
}: {
  seed: SeedInfo
  idx: number
  max: number
  nodes: GraphNode[]
  onNodeSelect?: (node: GraphNode) => void
}) {
  const pct = (seed.weight / max) * 100
  const isEntity = seed.signal === 'entity'
  const accentColor = isEntity ? 'var(--accent)' : 'var(--text-dim)'

  const handleClick = () => {
    if (!onNodeSelect) return
    const actualNode = nodes.find(n => n.id === seed.id)
    onNodeSelect(
      actualNode ?? {
        id: seed.id,
        name: seed.name.split('::').pop() || seed.name,
        file_path: '',
        label: 'Function',
        ppr_score: 0,
        is_seed: true,
        seed_weight: seed.weight,
      },
    )
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      style={{
        width: '100%',
        textAlign: 'left',
        padding: '10px 14px',
        display: 'grid',
        gridTemplateColumns: '22px 1fr auto',
        gap: 10,
        alignItems: 'center',
        border: 'none',
        borderBottom: '1px solid var(--border)',
        background: isEntity ? 'color-mix(in oklch, var(--accent-soft) 30%, transparent)' : 'transparent',
        cursor: 'pointer',
        fontFamily: 'inherit',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'color-mix(in oklch, var(--accent) 10%, transparent)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = isEntity
          ? 'color-mix(in oklch, var(--accent-soft) 30%, transparent)'
          : 'transparent'
      }}
    >
      <span className="font-mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
        {String(idx + 1).padStart(2, '0')}
      </span>
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 12,
            color: 'var(--text)',
            fontWeight: 500,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {seed.name}
        </div>
        <div style={{ marginTop: 2, fontSize: 10, color: accentColor }}>
          {isEntity ? 'Entity match' : 'BM25'}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, width: 52 }}>
        <span className="font-mono" style={{ fontSize: 10, color: accentColor, fontWeight: 600 }}>
          {seed.weight.toFixed(3)}
        </span>
        <div style={{ width: '100%', height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${pct}%`, height: '100%', background: accentColor }} />
        </div>
      </div>
    </button>
  )
}
