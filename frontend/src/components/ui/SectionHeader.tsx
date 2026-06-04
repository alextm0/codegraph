import type { ReactNode } from 'react'

interface SectionHeaderProps {
  label: string
  right?: ReactNode
  onClick?: () => void
  collapsible?: boolean
  collapsed?: boolean
}

export default function SectionHeader({
  label, right, onClick, collapsible, collapsed,
}: SectionHeaderProps) {
  return (
    <div
      style={{
        padding: '8px 12px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface2)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        cursor: collapsible ? 'pointer' : undefined,
      }}
      onClick={onClick}
    >
      <span
        style={{
          fontSize: 10,
          letterSpacing: '0.16em',
          color: 'var(--text-dim)',
          textTransform: 'uppercase',
        }}
      >
        {collapsible ? (collapsed ? '▸ ' : '▾ ') : ''}{collapsible ? label.replace(/^[▸▾]\s*/, '') : label}
      </span>
      {right}
    </div>
  )
}
