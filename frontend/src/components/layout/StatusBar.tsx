export interface WSStatus {
  type: 'file_changed' | 'rebuild_started' | 'rebuild_complete'
  path?: string
  timestamp: string
}

interface StatusBarProps {
  wsState: {
    lastMessage: WSStatus | null
    connected: boolean
  }
  nodeCount: number
  edgeCount: number
}

export default function StatusBar({ wsState, nodeCount, edgeCount }: StatusBarProps) {
  const { lastMessage, connected } = wsState
  const now = new Date().toLocaleTimeString('en-GB', { hour12: false })

  const syncMsg = lastMessage
    ? lastMessage.type === 'file_changed'
      ? `incremental.update on ${lastMessage.path ?? 'file_changed'}`
      : lastMessage.type === 'rebuild_complete'
      ? 'graph.synced ' + lastMessage.timestamp
      : 'graph.rebuilding…'
    : `graph.synced ${now}`

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
        fontSize: 9.5,
        color: 'var(--text-dim)',
        letterSpacing: '0.06em',
        flexShrink: 0,
      }}
    >
      <span style={{ color: connected ? 'var(--accent)' : 'var(--text-muted)' }}>
        ● {connected ? 'ws.connected' : 'ws.offline'}
      </span>
      <span>·</span>
      <span>{syncMsg}</span>

      <div style={{ flex: 1 }} />

      <span>n=<span style={{ color: 'var(--text)' }}>{nodeCount}</span></span>
      <span>e=<span style={{ color: 'var(--text)' }}>{edgeCount}</span></span>
      <span>p50=<span style={{ color: 'var(--text)' }}>8ms</span></span>
      <span>p95=<span style={{ color: 'var(--text)' }}>24ms</span></span>
    </div>
  )
}
