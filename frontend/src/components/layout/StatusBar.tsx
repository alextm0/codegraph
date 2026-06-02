import { useRef, useState } from 'react'
import type { WSStatus } from '../../hooks/useWebSocket'
import type { GraphStats } from '../../api/client'
import LatticeButton from '../ui/LatticeButton'
import StatsPopover from './StatsPopover'
import { formatDisplayTimestamp } from '../../utils/formatTime'

interface StatusBarProps {
  wsState: {
    lastMessage: WSStatus | null
    connected: boolean
  }
  nodeCount: number
  edgeCount: number
  graphStats?: GraphStats
  graphViewMode?: 'full' | 'query' | 'focus'
}

export default function StatusBar({
  wsState, nodeCount, edgeCount, graphStats,
  graphViewMode = 'full',
}: StatusBarProps) {
  const { connected, lastMessage } = wsState
  const [statsOpen, setStatsOpen] = useState(false)
  const statsBtnRef = useRef<HTMLButtonElement>(null)

  const syncMsg = lastMessage
    ? lastMessage.type === 'file_changed'
      ? `incremental update: ${lastMessage.path?.split('/').pop()}`
      : lastMessage.type === 'rebuild_progress'
      ? lastMessage.stage === 'parsing'
        ? `parsing ${lastMessage.files_parsed ?? 0}/${lastMessage.files_total ?? '?'}`
        : `building · ${lastMessage.node_count ?? 0} nodes`
      : lastMessage.type === 'rebuild_complete'
      ? `graph synced · ${formatDisplayTimestamp(lastMessage.timestamp ?? new Date())}`
      : lastMessage.type === 'rebuild_error'
      ? `rebuild failed: ${lastMessage.detail ?? 'error'}`
      : 'rebuilding graph…'
    : graphStats?.last_build
    ? `graph synced · ${formatDisplayTimestamp(graphStats.last_build)}`
    : 'graph ready'

  return (
    <>
      <div
        style={{
          gridColumn: '1 / -1',
          height: 'var(--statusbar-h)',
          borderTop: '1px solid var(--border)',
          background: 'var(--surface2)',
          display: 'grid',
          gridTemplateColumns: '1fr auto 1fr',
          alignItems: 'center',
          padding: '0 12px',
          fontSize: 9,
          color: 'var(--text-dim)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifySelf: 'start' }}>
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: connected ? 'var(--accent)' : 'var(--text-muted)',
              boxShadow: connected ? '0 0 8px var(--accent)' : 'none',
            }}
          />
          <span style={{ color: connected ? 'var(--text)' : 'var(--text-dim)' }}>{syncMsg}</span>
        </div>

        <div style={{ display: 'flex', gap: 12, fontVariantNumeric: 'tabular-nums', justifySelf: 'center' }}>
          {graphViewMode !== 'full' && (
            <span style={{ color: 'var(--accent)' }}>
              {graphViewMode === 'query' ? 'filtered' : 'file focus'}
            </span>
          )}
          <span>nodes: <span style={{ color: 'var(--text)', fontWeight: 600 }}>{nodeCount}</span></span>
          <span>edges: <span style={{ color: 'var(--text)', fontWeight: 600 }}>{edgeCount}</span></span>
        </div>

        <div style={{ display: 'flex', gap: 8, justifySelf: 'end' }}>
          <LatticeButton
            ref={statsBtnRef}
            variant="bracket"
            active={statsOpen}
            onClick={() => setStatsOpen(o => !o)}
            style={{ fontSize: 9, padding: '0 8px' }}
          >
            [stats]
          </LatticeButton>
        </div>
      </div>

      <StatsPopover
        stats={graphStats}
        open={statsOpen}
        onClose={() => setStatsOpen(false)}
        anchorRef={statsBtnRef}
      />
    </>
  )
}
