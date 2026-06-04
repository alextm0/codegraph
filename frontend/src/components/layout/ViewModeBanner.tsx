interface ViewModeBannerProps {
  nodeCount: number
}

/** Read-only indicator while viewing a file-focus subgraph (exit via Esc). */
export default function ViewModeBanner({ nodeCount }: ViewModeBannerProps) {
  const label = 'File focus'

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
        gap: 8,
        padding: '8px 14px',
        maxWidth: 'min(420px, calc(100% - 24px))',
        pointerEvents: 'none',
      }}
    >
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
      <span
        style={{
          fontSize: 10,
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.06em',
          flexShrink: 0,
        }}
      >
        Esc · full graph
      </span>
    </div>
  )
}
