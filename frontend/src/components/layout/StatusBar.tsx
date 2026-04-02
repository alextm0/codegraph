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

  return (
    <div
      style={{
        height: 24,
        background: 'var(--surface2)',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        fontSize: '0.75rem',
        color: 'var(--text-dim)',
        gap: 16,
        flexShrink: 0
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: connected ? '#22c55e' : '#ef4444'
        }} />
        {connected ? 'CONNECTED' : 'DISCONNECTED'}
      </div>

      <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {lastMessage ? (
          <>
            <span style={{ color: 'var(--accent)', marginRight: 8 }}>[{lastMessage.timestamp}]</span>
            {lastMessage.type === 'file_changed' && (
              <span>File changed: <code style={{ color: 'var(--text)' }}>{lastMessage.path || 'unknown path'}</code> (Incremental update applied)</span>
            )}
            {lastMessage.type === 'rebuild_started' && <span>Graph rebuild started...</span>}
            {lastMessage.type === 'rebuild_complete' && <span>Graph rebuild complete.</span>}
          </>
        ) : (
          'Ready'
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, opacity: 0.8 }}>
        <span>Nodes: <strong style={{ color: 'var(--text)' }}>{nodeCount}</strong></span>
        <span>Edges: <strong style={{ color: 'var(--text)' }}>{edgeCount}</strong></span>
      </div>
    </div>
  )
}
