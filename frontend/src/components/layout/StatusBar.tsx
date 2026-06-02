import type { WSStatus } from '../../hooks/useWebSocket'

interface StatusBarProps {
  wsState: {
    lastMessage: WSStatus | null
    connected: boolean
  }
  nodeCount: number
  edgeCount: number
  graphStats?: { nodes: Record<string, number>; edges: Record<string, number> }
}

export default function StatusBar({ wsState, nodeCount, edgeCount, graphStats }: StatusBarProps) {
  const { connected, lastMessage } = wsState
  const now = new Date().toLocaleTimeString('en-GB', { hour12: false })

  const syncMsg = lastMessage
    ? lastMessage.type === 'file_changed'
      ? `incremental update: ${lastMessage.path?.split('/').pop()}`
      : lastMessage.type === 'rebuild_progress'
      ? lastMessage.stage === 'parsing'
        ? `parsing ${lastMessage.files_parsed ?? 0}/${lastMessage.files_total ?? '?'} ${lastMessage.current_file ?? ''}`.trim()
        : `building graph · ${lastMessage.node_count ?? 0} nodes · ${lastMessage.edge_count ?? 0} edges`
      : lastMessage.type === 'rebuild_complete'
      ? `graph synced: ${lastMessage.timestamp}`
      : lastMessage.type === 'rebuild_error'
      ? `rebuild failed: ${lastMessage.detail ?? 'error'}`
      : 'rebuilding graph...'
    : `graph synced: ${now}`

  return (
    <div
      style={{
        gridColumn: '1 / -1',
        height: 'var(--statusbar-h)',
        borderTop: '1px solid var(--border)',
        background: 'var(--surface2)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        gap: 16,
        fontSize: 9,
        color: 'var(--text-dim)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: connected ? 'var(--accent)' : 'var(--text-muted)',
            boxShadow: connected ? '0 0 8px var(--accent)' : 'none',
            transition: 'all 0.3s ease',
          }}
        />
        <span style={{ color: connected ? 'var(--text)' : 'var(--text-dim)' }}>
          {syncMsg}
        </span>
      </div>

      <div style={{ flex: 1 }} />

      <div style={{ display: 'flex', gap: 16, alignItems: 'center', fontFamily: 'var(--font-mono)' }}>
        <span>nodes: <span style={{ color: 'var(--text)', fontWeight: 600 }}>{nodeCount}</span></span>
        <span>edges: <span style={{ color: 'var(--text)', fontWeight: 600 }}>{edgeCount}</span></span>
        {graphStats && (
          <span style={{ color: 'var(--text-dim)', fontSize: 8 }}>
            fn {graphStats.nodes.Function ?? 0} · cls {graphStats.nodes.Class ?? 0} · calls{' '}
            {graphStats.edges.CALLS ?? 0}
          </span>
        )}
      </div>
    </div>
  )
}
