import { useRef, useEffect } from 'react'
import type { GraphStats } from '../../api/client'
import LatticeButton from '../ui/LatticeButton'
import { formatDateTime } from '../../utils/formatTime'

interface StatsPopoverProps {
  stats: GraphStats | undefined
  open: boolean
  onClose: () => void
  anchorRef: React.RefObject<HTMLElement | null>
}

export default function StatsPopover({ stats, open, onClose, anchorRef }: StatsPopoverProps) {
  const popRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      const t = e.target as Node
      if (popRef.current?.contains(t) || anchorRef.current?.contains(t)) return
      onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open, onClose, anchorRef])

  if (!open || !stats) return null

  const totalNodes = Object.values(stats.nodes).reduce((a, b) => a + b, 0)
  const totalEdges = Object.values(stats.edges).reduce((a, b) => a + b, 0)

  return (
    <div
      ref={popRef}
      style={{
        position: 'fixed',
        bottom: 'calc(var(--statusbar-h) + 8px)',
        right: 12,
        width: 320,
        maxHeight: 420,
        overflowY: 'auto',
        background: 'var(--surface2)',
        border: '1px solid var(--border)',
        boxShadow: 'var(--shadow)',
        zIndex: 1000,
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 10, letterSpacing: '0.12em', color: 'var(--text-dim)', textTransform: 'uppercase' }}>
          Graph statistics
        </span>
        <LatticeButton variant="ghost" onClick={onClose} style={{ padding: 0, fontSize: 12 }}>×</LatticeButton>
      </div>

      {stats.last_build && (
        <div style={{ padding: '8px 12px', fontSize: 9, color: 'var(--text-muted)', borderBottom: '1px dashed var(--border)' }}>
          last build · {formatDateTime(stats.last_build)}
        </div>
      )}

      <StatsTable title="Nodes" rows={stats.nodes} total={totalNodes} />
      <StatsTable title="Edges" rows={stats.edges} total={totalEdges} />

      {stats.most_connected_files && stats.most_connected_files.length > 0 && (
        <div style={{ padding: '8px 12px 12px' }}>
          <div style={sectionLabel}>Top files by entity count</div>
          {stats.most_connected_files.map(row => (
            <div key={row.file_path} style={{ display: 'flex', gap: 8, fontSize: 10, padding: '3px 0' }}>
              <span style={{ color: 'var(--accent)', minWidth: 28, textAlign: 'right' }}>{row.entity_count}</span>
              <span style={{ color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.file_path}>
                {row.file_path}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatsTable({ title, rows, total }: { title: string; rows: Record<string, number>; total: number }) {
  return (
    <div style={{ padding: '8px 12px', borderBottom: '1px dashed var(--border)' }}>
      <div style={sectionLabel}>{title}</div>
      {Object.entries(rows).sort(([a], [b]) => a.localeCompare(b)).map(([label, count]) => (
        <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, padding: '2px 0' }}>
          <span style={{ color: 'var(--text-dim)' }}>{label}</span>
          <span style={{ color: 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>{count}</span>
        </div>
      ))}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, paddingTop: 4, marginTop: 4, borderTop: '1px solid var(--border)', fontWeight: 600 }}>
        <span>TOTAL</span>
        <span>{total}</span>
      </div>
    </div>
  )
}

const sectionLabel: React.CSSProperties = {
  fontSize: 9,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: 'var(--text-muted)',
  marginBottom: 6,
}
