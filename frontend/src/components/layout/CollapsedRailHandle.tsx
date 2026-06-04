interface CollapsedRailHandleProps {
  onOpen: () => void
}

/** Mid-left tab to reopen the collapsed project rail. */
export default function CollapsedRailHandle({ onOpen }: CollapsedRailHandleProps) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="focus-ring"
      title="Open sidebar"
      style={{
        position: 'absolute',
        left: 0,
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 25,
        width: 28,
        height: 56,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--overlay)',
        backdropFilter: 'blur(10px)',
        border: '1px solid var(--border)',
        borderLeft: 'none',
        borderRadius: '0 var(--radius-md) var(--radius-md) 0',
        boxShadow: 'var(--elev-1)',
        color: 'var(--text-muted)',
        cursor: 'pointer',
        fontSize: 14,
        transition: 'color var(--dur-fast), border-color var(--dur-fast)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.color = 'var(--accent)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.color = 'var(--text-muted)'
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      ›
    </button>
  )
}
