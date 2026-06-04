type BadgeVariant = 'default' | 'accent' | 'seed' | 'entity'

const LABEL_SHORT: Record<string, string> = {
  File: 'FILE',
  Class: 'CLASS',
  Function: 'FN',
  Method: 'MTH',
}

interface LatticeBadgeProps {
  label: string
  variant?: BadgeVariant
  entityLabel?: string
}

export default function LatticeBadge({ label, variant = 'default', entityLabel }: LatticeBadgeProps) {
  const text = entityLabel ? (LABEL_SHORT[entityLabel] ?? entityLabel.slice(0, 3).toUpperCase()) : label

  const colors: Record<BadgeVariant, React.CSSProperties> = {
    default: { background: 'var(--surface2)', color: 'var(--text-dim)' },
    accent:  { background: 'var(--accent)', color: 'var(--bg)' },
    seed:    { background: 'var(--seed)', color: 'var(--bg)' },
    entity:  { background: 'var(--accent-soft)', color: 'var(--accent-ink)' },
  }

  return (
    <span
      style={{
        padding: '2px 8px',
        fontSize: 10,
        letterSpacing: '0.06em',
        fontWeight: 600,
        borderRadius: 'var(--radius-sm)',
        flexShrink: 0,
        fontFamily: 'var(--font-mono)',
        ...colors[variant],
      }}
    >
      {text}
    </span>
  )
}
