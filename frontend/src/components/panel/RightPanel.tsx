import { useState, useEffect, useRef } from 'react'
import { getNodeDetail, openInIDE } from '../../api/client'
import type { GraphNode, NodeDetailResponse, NodeRelation, SeedInfo } from '../../types/api'
import LatticeButton from '../ui/LatticeButton'
import LatticeBadge from '../ui/LatticeBadge'
import IconButton from '../ui/IconButton'

interface RightPanelProps {
  selectedNode: GraphNode | null
  onClose: () => void
  onNodeSelect: (node: GraphNode | null) => void
  width?: number
  seeds?: SeedInfo[]
  embedded?: boolean
}

export default function RightPanel({
  selectedNode, onClose, onNodeSelect,
  width = 380, seeds = [], embedded = false,
}: RightPanelProps) {
  const [detail, setDetail] = useState<NodeDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [ideError, setIdeError] = useState<string | null>(null)
  const reqIdRef = useRef(0)

  const seedMeta = seeds.find(s => s.id === selectedNode?.id)

  useEffect(() => {
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
        width: embedded ? '100%' : width,
        background: 'var(--surface)',
        borderLeft: embedded ? 'none' : '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        zIndex: 10,
        flexShrink: 0,
        overflow: 'hidden',
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', background: 'var(--surface2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <span style={{ fontSize: 10, letterSpacing: '0.12em', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>
          {embedded ? selectedNode.name : 'Node Inspector'}
        </span>
        <IconButton onClick={onClose} title="Clear selection">×</IconButton>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
        <div style={{ padding: 12, borderBottom: '1px dashed var(--border)' }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <LatticeBadge label={selectedNode.label.toUpperCase()} variant="accent" />
            {selectedNode.is_seed && <LatticeBadge label="SEED" variant="seed" />}
          </div>
          <div style={{ fontSize: 14, color: 'var(--text)', fontWeight: 600, wordBreak: 'break-word' }}>
            {selectedNode.name}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <span style={{ wordBreak: 'break-all' }}>{selectedNode.file_path}</span>
            <LatticeButton
              variant="secondary"
              onClick={() => {
                const line = selectedNode.line_number || detail?.node?.line_number || 1
                setIdeError(null)
                openInIDE(selectedNode.file_path, line).catch(() => {
                  setIdeError('Failed to open in IDE. Install cursor or code CLI.')
                })
              }}
              style={{ padding: '2px 8px', fontSize: 9, flexShrink: 0 }}
            >
              ↗ IDE
            </LatticeButton>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: selectedNode.is_seed ? '1fr 1fr' : '1fr', borderBottom: '1px dashed var(--border)' }}>
          <div style={{ padding: 12, borderRight: selectedNode.is_seed ? '1px dashed var(--border)' : 'none' }}>
            <div style={statLabel}>relevance</div>
            <div style={{ fontSize: 18, color: 'var(--accent)', fontVariantNumeric: 'tabular-nums slashed-zero' }}>
              {(selectedNode.ppr_score || 0).toFixed(5)}
            </div>
          </div>
          {selectedNode.is_seed && (
            <div style={{ padding: 12 }}>
              <div style={statLabel}>seed weight</div>
              <div style={{ fontSize: 18, color: 'var(--seed)', fontVariantNumeric: 'tabular-nums slashed-zero' }}>
                {(selectedNode.seed_weight || 0).toFixed(3)}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 4 }}>
                {seedMeta?.signal === 'entity' ? 'entity match' : 'bm25'}
              </div>
            </div>
          )}
        </div>

        {ideError && (
          <div style={{ padding: '8px 12px', fontSize: 10, color: 'var(--danger)' }}>{ideError}</div>
        )}

        {loading ? (
          <div style={{ padding: 12, fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic' }}>// loading…</div>
        ) : detail ? (
          <>
            {(detail.incoming.length > 0 || detail.outgoing.length > 0) && (
              <div style={{ padding: 12, borderBottom: '1px dashed var(--border)' }}>
                {detail.incoming.length > 0 && (
                  <>
                    <div style={statLabel}>Incoming</div>
                    {detail.incoming.map((rel, i) => (
                      <RelationRow key={`in-${i}`} rel={rel} direction="incoming" onNodeSelect={onNodeSelect} />
                    ))}
                  </>
                )}
                {detail.outgoing.length > 0 && (
                  <>
                    <div style={{ ...statLabel, marginTop: detail.incoming.length ? 8 : 0 }}>Outgoing</div>
                    {detail.outgoing.map((rel, i) => (
                      <RelationRow key={`out-${i}`} rel={rel} direction="outgoing" onNodeSelect={onNodeSelect} />
                    ))}
                  </>
                )}
              </div>
            )}

            {detail.source_snippet && (
              <div style={{ padding: 12 }}>
                <div style={statLabel}>source</div>
                <pre style={{ margin: 0, padding: 10, background: 'var(--bg)', border: '1px solid var(--border)', fontSize: 10.5, color: 'var(--text)', lineHeight: 1.55, overflowX: 'auto', maxHeight: 220, whiteSpace: 'pre' }}>
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

function RelationRow({ rel, direction, onNodeSelect }: {
  rel: NodeRelation
  direction: 'incoming' | 'outgoing'
  onNodeSelect: (node: GraphNode) => void
}) {
  return (
    <div
      style={{ display: 'grid', gridTemplateColumns: '20px 90px 1fr auto', gap: 6, padding: '4px 0', alignItems: 'center', fontSize: 11, cursor: 'pointer' }}
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
      onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface2)' }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
    >
      <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{direction === 'incoming' ? '⟵' : '⟶'}</span>
      <span style={{ color: 'var(--accent)', fontSize: 9, letterSpacing: '0.08em', textTransform: 'uppercase' }}>{rel.relationship}</span>
      <span style={{ color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={rel.qualified_name}>{rel.name}</span>
      <span style={{ color: 'var(--text-muted)', fontSize: 9 }}>◎</span>
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
