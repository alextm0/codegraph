interface ClearSelectionPillProps {
  visible: boolean
  label?: string
  onClear: () => void
}

/** Subtle floating control to clear graph selection / connect mode. */
export default function ClearSelectionPill({ visible, label = 'Clear', onClear }: ClearSelectionPillProps) {
  if (!visible) return null

  return (
    <button
      type="button"
      onClick={onClear}
      className="focus-ring"
      style={{
        position: 'absolute',
        bottom: 36,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 17,
        padding: '6px 14px',
        fontSize: 11,
        fontFamily: 'var(--font-body)',
        color: 'var(--text-muted)',
        background: 'var(--overlay)',
        backdropFilter: 'blur(10px)',
        border: '1px solid var(--border)',
        borderRadius: 999,
        boxShadow: 'var(--elev-1)',
        cursor: 'pointer',
        opacity: 0.72,
        transition: 'opacity var(--dur-fast), color var(--dur-fast), border-color var(--dur-fast)',
        animation: 'fade-in 200ms var(--ease) forwards',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.opacity = '1'
        e.currentTarget.style.color = 'var(--text)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.opacity = '0.72'
        e.currentTarget.style.color = 'var(--text-muted)'
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
      title="Clear selection (Esc)"
    >
      {label} · Esc
    </button>
  )
}
