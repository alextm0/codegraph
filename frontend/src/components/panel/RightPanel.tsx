import { useState, useEffect, useRef } from 'react'
import { getNodeDetail, openInIDE, getDependencies, getDependenciesGraph } from '../../api/client'
import type { GraphData, GraphNode, NodeDetailResponse, NodeRelation, SeedInfo } from '../../types/api'

interface RightPanelProps {
  selectedNode: GraphNode | null
  onClose: () => void
  onNodeSelect: (node: GraphNode | null) => void
  onDepsGraph?: (graph: GraphData) => void
  width?: number
  seeds?: SeedInfo[]
}

export default function RightPanel({
  selectedNode, onClose, onNodeSelect, onDepsGraph, width = 380, seeds = [],
}: RightPanelProps) {
  const [detail, setDetail] = useState<NodeDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [ideError, setIdeError] = useState<string | null>(null)
  const [extraRelations, setExtraRelations] = useState<NodeRelation[]>([])
  const [depsLoading, setDepsLoading] = useState(false)
  const reqIdRef = useRef(0)

  const seedMeta = seeds.find(s => s.id === selectedNode?.id)

  useEffect(() => {
    setExtraRelations([])
    setIdeError(null)
    if (!selectedNode) { setDetail(null); setLoading(false); return }
    const id = ++reqIdRef.current
    setLoading(true)
    setDetail(null)
    getNodeDetail(selectedNode.id)
      .then(res => { if (id === reqIdRef.current) setDetail(res) })
      .catch(err => { if (id === reqIdRef.current) console.error('node detail', err) })
      .finally(() => { if (id === reqIdRef.current) setLoading(false) })
  }, [selectedNode])

  if (!selectedNode) return null

  return (
    <div
      style={{
        width,
        background: 'var(--surface)',
        borderLeft: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        zIndex: 10,
        flexShrink: 0,
        overflow: 'hidden',
        fontFamily: 'var(--font-mono)',
      }}
    >
      {/* Node Inspector header */}
      <div
        style={{
          padding: '8px 12px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface2)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 10,
            letterSpacing: '0.12em',
            color: 'var(--text-dim)',
            textTransform: 'uppercase',
            fontWeight: 600,
          }}
        >
          Node Inspector
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <IconBtn onClick={onClose} title="Close">×</IconBtn>
        </div>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
        {/* Identity */}
        <div
          style={{
            padding: 12,
            borderBottom: '1px dashed var(--border)',
          }}
        >
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <Badge label={selectedNode.label.toUpperCase()} accent />
            {selectedNode.is_seed && <Badge label="SEED" seed />}
          </div>
          <div
            style={{
              fontSize: 14,
              color: 'var(--text)',
              fontWeight: 600,
              wordBreak: 'break-word',
              letterSpacing: '0.02em',
            }}
          >
            {selectedNode.name}
          </div>
          <div
            style={{
              fontSize: 10,
              color: 'var(--text-muted)',
              marginTop: 4,
              wordBreak: 'break-all',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: 8,
            }}
          >
            <span>{selectedNode.file_path}</span>
            <button
              onClick={() => {
                const line = selectedNode.line_number || detail?.node?.line_number || 1
                setIdeError(null)
                openInIDE(selectedNode.file_path, line).catch(err => {
                  setIdeError('Failed to open in IDE. Install cursor or code CLI.')
                  console.error('Failed to open in IDE', err)
                })
              }}
              style={{
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                color: 'var(--text-dim)',
                fontSize: 9,
                padding: '2px 6px',
                cursor: 'pointer',
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                transition: 'all 100ms',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.color = 'var(--text)'
                e.currentTarget.style.borderColor = 'var(--accent)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.color = 'var(--text-dim)'
                e.currentTarget.style.borderColor = 'var(--border)'
              }}
            >
              <span style={{ fontSize: 10 }}>↗</span> IDE
            </button>
          </div>
        </div>

        {/* Stats grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: selectedNode.is_seed ? '1fr 1fr' : '1fr',
            borderBottom: '1px dashed var(--border)',
          }}
        >
          <div style={{ padding: 12, borderRight: selectedNode.is_seed ? '1px dashed var(--border)' : 'none' }}>
            <div style={statLabel}>relevance</div>
            <div
              style={{
                fontSize: 18,
                color: 'var(--accent)',
                fontVariantNumeric: 'tabular-nums slashed-zero',
              }}
            >
              {(selectedNode.ppr_score || 0).toFixed(5)}
            </div>
          </div>
          {selectedNode.is_seed && (
            <div style={{ padding: 12 }}>
              <div style={statLabel}>seed signal</div>
              <div style={{ fontSize: 11, color: 'var(--seed)', marginBottom: 6 }}>
                {seedMeta?.signal === 'entity' ? 'entity_match (0.6)' : 'bm25 (0.3)'}
              </div>
              <div style={statLabel}>seed weight</div>
              <div
                style={{
                  fontSize: 18,
                  color: 'var(--seed)',
                  fontVariantNumeric: 'tabular-nums slashed-zero',
                }}
              >
                {(selectedNode.seed_weight || 0).toFixed(3)}
              </div>
            </div>
          )}
        </div>

        {ideError && (
          <div style={{ padding: '8px 12px', fontSize: 10, color: 'oklch(0.80 0.14 25)' }}>{ideError}</div>
        )}

        <div style={{ padding: '8px 12px', borderBottom: '1px dashed var(--border)', display: 'flex', gap: 6 }}>
          {(['upstream', 'downstream', 'both'] as const).map(dir => (
            <button
              key={dir}
              type="button"
              disabled={depsLoading}
              onClick={() => {
                setDepsLoading(true)
                const entityId = selectedNode.id
                Promise.all([
                  getDependencies(entityId, dir, 1),
                  getDependenciesGraph(entityId, dir, 1),
                ])
                  .then(([res, graphRes]) => {
                    setExtraRelations(
                      res.results.map(r => ({
                        qualified_name: r.qualified_name,
                        name: r.name,
                        label: r.label,
                        file_path: r.file_path,
                        relationship: r.relationship_type,
                      })),
                    )
                    onDepsGraph?.(graphRes.graph)
                  })
                  .catch(console.error)
                  .finally(() => setDepsLoading(false))
              }}
              style={{
                flex: 1,
                fontSize: 9,
                padding: '4px 6px',
                border: '1px solid var(--border)',
                background: 'var(--surface2)',
                color: 'var(--text-dim)',
                cursor: 'pointer',
              }}
            >
              {dir}
            </button>
          ))}
        </div>

        {/* Relations + source */}
        {loading ? (
          <div
            style={{
              padding: 12,
              fontSize: 10,
              color: 'var(--text-muted)',
              fontStyle: 'italic',
            }}
          >
            // loading…
          </div>
        ) : detail ? (
          <>
            {(detail.incoming.length > 0 || detail.outgoing.length > 0 || extraRelations.length > 0) && (
              <div style={{ padding: 12, borderBottom: '1px dashed var(--border)' }}>
                <div style={statLabel}>relations</div>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {detail.incoming.map((rel, i) => (
                    <RelationRow
                      key={`in-${i}`}
                      rel={rel}
                      direction="incoming"
                      onNodeSelect={onNodeSelect}
                    />
                  ))}
                  {detail.outgoing.map((rel, i) => (
                    <RelationRow
                      key={`out-${i}`}
                      rel={rel}
                      direction="outgoing"
                      onNodeSelect={onNodeSelect}
                    />
                  ))}
                  {extraRelations.map((rel, i) => (
                    <RelationRow
                      key={`dep-${i}`}
                      rel={rel}
                      direction="outgoing"
                      onNodeSelect={onNodeSelect}
                    />
                  ))}
                </div>
              </div>
            )}

            {detail.source_snippet && (
              <div style={{ padding: 12 }}>
                <div style={statLabel}>source</div>
                <pre
                  style={{
                    margin: 0,
                    padding: 10,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    fontSize: 10.5,
                    color: 'var(--text)',
                    lineHeight: 1.55,
                    overflowX: 'auto',
                    maxHeight: 220,
                    whiteSpace: 'pre',
                  }}
                >
                  {detail.source_snippet}
                </pre>
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  )
}

/* ── Sub-components ──────────────────────────────────────── */
function Badge({ label, accent, seed }: { label: string; accent?: boolean; seed?: boolean }) {
  return (
    <span
      style={{
        padding: '2px 6px',
        background: seed ? 'var(--seed)' : accent ? 'var(--accent)' : 'var(--surface2)',
        color: seed || accent ? 'var(--bg)' : 'var(--text-dim)',
        fontSize: 9,
        letterSpacing: '0.14em',
        fontWeight: 600,
      }}
    >
      {label}
    </span>
  )
}

function IconBtn({ children, onClick, title }: {
  children: React.ReactNode
  onClick: () => void
  title?: string
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        background: 'transparent',
        border: 'none',
        color: 'var(--text-dim)',
        cursor: 'pointer',
        fontSize: 16,
        padding: '0 4px',
        lineHeight: 1,
        transition: 'color 100ms',
        fontFamily: 'var(--font-mono)',
      }}
      onMouseEnter={e => { e.currentTarget.style.color = 'var(--text)' }}
      onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-dim)' }}
    >
      {children}
    </button>
  )
}

function RelationRow({ rel, direction, onNodeSelect }: {
  rel: NodeRelation
  direction: 'incoming' | 'outgoing'
  onNodeSelect: (node: GraphNode) => void
}) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '20px 100px 1fr auto',
        gap: 8,
        padding: '4px 0',
        alignItems: 'center',
        fontSize: 11,
        borderBottom: '1px solid transparent',
        transition: 'background 100ms',
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--surface2)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
    >
      <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>
        {direction === 'incoming' ? '⟵' : '⟶'}
      </span>
      <span
        style={{
          color: 'var(--accent)',
          fontSize: 9,
          letterSpacing: '0.10em',
          textTransform: 'uppercase',
        }}
      >
        {rel.relationship}
      </span>
      <span
        style={{
          color: 'var(--text)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={rel.qualified_name}
      >
        {rel.name}
      </span>
      <IconBtn
        onClick={() =>
          onNodeSelect({
            id: rel.qualified_name,
            name: rel.name,
            file_path: rel.file_path,
            label: rel.label as GraphNode['label'],
            ppr_score: 0,
            is_seed: false,
            seed_weight: 0,
          })
        }
        title="Focus node"
      >
        ◎
      </IconBtn>
    </div>
  )
}

const statLabel: React.CSSProperties = {
  fontSize: 9,
  color: 'var(--text-muted)',
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  marginBottom: 4,
}
