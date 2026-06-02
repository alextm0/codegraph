import { useEffect, useRef, useState } from 'react'
import { getFile, openInIDE } from '../../api/client'
import type { GraphNode } from '../../types/api'
import LatticeBadge from '../ui/LatticeBadge'
import LatticeButton from '../ui/LatticeButton'
import IconButton from '../ui/IconButton'

interface FilePanelProps {
  filePath: string
  graphNodes: GraphNode[]
  onNodeSelect: (node: GraphNode) => void
  onClose: () => void
  activeNode?: GraphNode | null
}

export default function FilePanel({
  filePath,
  graphNodes,
  onNodeSelect,
  onClose,
  activeNode = null,
}: FilePanelProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const activeLineRef = useRef<HTMLDivElement | null>(null)

  const localEntities = graphNodes.filter(n => n.file_path === filePath)

  const activeStart = activeNode?.file_path === filePath ? activeNode.line_number : undefined
  const activeEnd = activeNode?.file_path === filePath ? activeNode.line_end : undefined

  useEffect(() => {
    setLoading(true)
    setError(null)
    getFile(filePath)
      .then(res => setContent(res.content))
      .catch(err => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false))
  }, [filePath])

  useEffect(() => {
    if (!loading && content !== null && activeStart) {
      activeLineRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [loading, content, activeStart, filePath])

  const lines = content?.split('\n') ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div
        style={{
          padding: '10px 12px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface2)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
              {filePath.split('/').pop()}
            </div>
            <div
              className="font-mono"
              style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, wordBreak: 'break-all' }}
            >
              {filePath}
            </div>
          </div>
          <IconButton onClick={onClose} title="Close">×</IconButton>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <LatticeButton
            variant="secondary"
            onClick={() => openInIDE(filePath, 1).catch(() => {})}
            style={{ fontSize: 11, padding: '4px 10px' }}
          >
            Open in IDE
          </LatticeButton>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center' }}>
            {localEntities.length} entities
          </span>
        </div>
      </div>

      {localEntities.length > 0 && (
        <div
          style={{
            padding: '8px 12px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
            flexShrink: 0,
            maxHeight: 88,
            overflowY: 'auto',
          }}
        >
          {localEntities.map(n => {
            const chipActive = n.id === activeNode?.id
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => onNodeSelect(n)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 8px',
                  background: chipActive
                    ? 'color-mix(in oklch, var(--accent) 18%, transparent)'
                    : 'var(--surface2)',
                  border: `1px solid ${chipActive ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                }}
              >
                <LatticeBadge entityLabel={n.label} label="" variant="entity" />
                <span style={{ fontSize: 11, color: chipActive ? 'var(--accent)' : 'var(--text)' }}>{n.name}</span>
              </button>
            )
          })}
        </div>
      )}

      <div style={{ flex: 1, overflow: 'auto', minHeight: 0, background: 'var(--bg)' }}>
        {loading && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--text-muted)' }}>Loading source…</div>
        )}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--danger)' }}>{error}</div>
        )}
        {content !== null && !loading && (
          <div
            style={{
              fontSize: 11,
              lineHeight: 1.55,
              fontFamily: 'var(--font-mono)',
              padding: '12px 0',
            }}
          >
            {lines.map((ln, i) => {
              const n = i + 1
              const active =
                activeStart !== undefined &&
                n >= activeStart &&
                n <= (activeEnd ?? activeStart)
              const isFirstActive = active && n === activeStart
              return (
                <div
                  key={i}
                  ref={isFirstActive ? activeLineRef : undefined}
                  style={{
                    display: 'flex',
                    background: active
                      ? 'color-mix(in oklch, var(--accent) 12%, transparent)'
                      : 'transparent',
                    borderLeft: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
                  }}
                >
                  <span
                    style={{
                      width: 46,
                      flexShrink: 0,
                      textAlign: 'right',
                      padding: '0 10px 0 0',
                      marginRight: 12,
                      color: active ? 'var(--accent)' : 'var(--text-muted)',
                      userSelect: 'none',
                      borderRight: '1px solid var(--border)',
                    }}
                  >
                    {n}
                  </span>
                  <span style={{ whiteSpace: 'pre', color: 'var(--text)', flex: 1, paddingRight: 12 }}>
                    {ln || ' '}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
