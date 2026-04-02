import { useState, useEffect, useRef } from 'react'
import { getNodeDetail, openFile } from '../../api/client'
import type { GraphNode, NodeDetailResponse } from '../../types/api'

interface RightPanelProps {
  selectedNode: GraphNode | null
  onClose: () => void
  onNodeSelect: (node: GraphNode | null) => void
  width?: number
}

export default function RightPanel({ selectedNode, onClose, onNodeSelect, width = 380 }: RightPanelProps) {
  const [detail, setDetail] = useState<NodeDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const requestIdRef = useRef<number>(0)

  useEffect(() => {
    if (selectedNode) {
      const currentRequestId = ++requestIdRef.current
      setLoading(true)
      setDetail(null)
      getNodeDetail(selectedNode.id)
        .then(res => {
          if (currentRequestId === requestIdRef.current) {
            setDetail(res)
          }
        })
        .catch(err => {
          if (currentRequestId === requestIdRef.current) {
            console.error('Failed to fetch node detail', err)
          }
        })
        .finally(() => {
          if (currentRequestId === requestIdRef.current) {
            setLoading(false)
          }
        })
    } else {
      setDetail(null)
      setLoading(false)
    }
  }, [selectedNode])

  if (!selectedNode) return null

  return (
    <div
      style={{
        width: width,
        backgroundColor: 'var(--surface)',
        borderLeft: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        zIndex: 10,
        boxShadow: '-4px 0 16px rgba(0,0,0,0.3)'
      }}
    >
      <div style={{ padding: 12, borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Node Detail</h3>
        <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text)', cursor: 'pointer', fontSize: '1.2rem' }}>×</button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        {/* Identity — always shown from selectedNode immediately */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <section>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{
                backgroundColor: `var(--node-${selectedNode.label.toLowerCase()})`,
                color: 'black',
                padding: '2px 6px',
                borderRadius: 4,
                fontSize: '0.7rem',
                fontWeight: 'bold',
              }}>
                {selectedNode.label.toUpperCase()}
              </span>
              {selectedNode.is_seed && (
                <span style={{ backgroundColor: '#fbbf24', color: 'black', padding: '2px 6px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 'bold' }}>SEED</span>
              )}
              {selectedNode.file_path && (
                <button
                  onClick={() => openFile(selectedNode.file_path!).catch(console.error)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--text)',
                    opacity: 0.6,
                    fontSize: '1.2rem',
                    padding: '0 4px',
                    marginLeft: 'auto',
                  }}
                  title="Open in Editor"
                  onMouseEnter={e => e.currentTarget.style.opacity = '1'}
                  onMouseLeave={e => e.currentTarget.style.opacity = '0.6'}
                >
                  ↗
                </button>
              )}
            </div>
            <h2 style={{ margin: '4px 0', fontSize: '1.2rem', wordBreak: 'break-all' }}>{selectedNode.name}</h2>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>{selectedNode.id}</div>
          </section>

          {/* Stats — from selectedNode (has PPR scores) */}
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1, backgroundColor: 'var(--surface2)', padding: 10, borderRadius: 8 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 2 }}>PPR SCORE</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>{(selectedNode.ppr_score || 0).toFixed(5)}</div>
            </div>
            {selectedNode.is_seed && (
              <div style={{ flex: 1, backgroundColor: 'var(--surface2)', padding: 10, borderRadius: 8 }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 2 }}>SEED WEIGHT</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>{(selectedNode.seed_weight || 0).toFixed(4)}</div>
              </div>
            )}
          </div>

          {/* Relations and source — loaded async */}
          {loading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading details…</div>
          ) : detail ? (
            <>
              <section>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '0.9rem', color: 'var(--text-muted)' }}>RELATIONS</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {detail.incoming.map((rel, i) => (
                    <RelationRow key={`in-${i}`} rel={rel} direction="incoming" onNodeSelect={onNodeSelect} />
                  ))}
                  {detail.outgoing.map((rel, i) => (
                    <RelationRow key={`out-${i}`} rel={rel} direction="outgoing" onNodeSelect={onNodeSelect} />
                  ))}
                  {detail.incoming.length === 0 && detail.outgoing.length === 0 && (
                    <div style={{ fontSize: '0.85rem', fontStyle: 'italic', color: 'var(--text-muted)' }}>No direct relations</div>
                  )}
                </div>
              </section>

              {detail.source_snippet && (
                <section>
                  <h4 style={{ margin: '0 0 8px 0', fontSize: '0.9rem', color: 'var(--text-muted)' }}>SOURCE</h4>
                  <pre style={{
                    backgroundColor: 'var(--bg)',
                    padding: 12,
                    borderRadius: 8,
                    fontSize: '0.8rem',
                    fontFamily: 'var(--mono)',
                    overflowX: 'auto',
                    border: '1px solid var(--border)',
                  }}>
                    <code>{detail.source_snippet}</code>
                  </pre>
                </section>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function RelationRow({ rel, direction, onNodeSelect }: { rel: any, direction: 'incoming' | 'outgoing', onNodeSelect: (node: GraphNode) => void }) {
  const handleFocus = () => {
    onNodeSelect({
      id: rel.qualified_name,
      name: rel.name,
      file_path: rel.file_path,
      label: rel.label,
      ppr_score: 0,
      is_seed: false,
      seed_weight: 0
    })
  }

  const handleOpen = () => {
    if (rel.file_path) {
      openFile(rel.file_path).catch(console.error)
    }
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      fontSize: '0.85rem',
      backgroundColor: 'var(--surface2)',
      padding: '6px 10px',
      borderRadius: 6,
      border: '1px solid transparent',
      transition: 'border-color 0.1s'
    }}>
      <span style={{ fontSize: '0.7rem', opacity: 0.6, width: 60, flexShrink: 0 }}>
        {direction === 'incoming' ? '⟵' : '⟶'} {rel.relationship}
      </span>
      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={rel.qualified_name}>
        {rel.name}
      </span>
      {rel.file_path && (
        <button
          onClick={handleOpen}
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text)', opacity: 0.5, padding: '0 4px', fontSize: '1rem' }}
          title="Open in Editor"
          onMouseEnter={e => e.currentTarget.style.opacity = '1'}
          onMouseLeave={e => e.currentTarget.style.opacity = '0.5'}
        >
          ↗
        </button>
      )}
      <button
        onClick={handleFocus}
        style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text)', opacity: 0.5, padding: '0 4px', fontSize: '1rem' }}
        title="Focus Node"
        onMouseEnter={e => e.currentTarget.style.opacity = '1'}
        onMouseLeave={e => e.currentTarget.style.opacity = '0.5'}
      >
        ☉
      </button>
    </div>
  )
}
