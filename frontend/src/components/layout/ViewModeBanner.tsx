import LatticeButton from '../ui/LatticeButton'

interface ViewModeBannerProps {
  mode: 'query' | 'focus'
  nodeCount: number
  onShowAll: () => void
}

/** Control to exit query / file-focus and return to the full codebase graph. */
export default function ViewModeBanner({ mode, nodeCount, onShowAll }: ViewModeBannerProps) {
  const label = mode === 'query' ? 'Query results' : 'File focus'

  return (
    <div
      className="surface-elevated"
      style={{
        position: 'absolute',
        top: 12,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 16,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '8px 10px 8px 14px',
        maxWidth: 'min(420px, calc(100% - 24px))',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'var(--accent)',
            flexShrink: 0,
            boxShadow: '0 0 6px var(--accent)',
          }}
        />
        <span
          style={{
            fontSize: 12,
            color: 'var(--text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {label}
          <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
            {' '}
            · {nodeCount.toLocaleString()} nodes
          </span>
        </span>
      </div>
      <LatticeButton
        variant="primary"
        onClick={onShowAll}
        style={{ fontSize: 11, padding: '6px 12px', flexShrink: 0, whiteSpace: 'nowrap' }}
      >
        Entire codebase
      </LatticeButton>
    </div>
  )
}
