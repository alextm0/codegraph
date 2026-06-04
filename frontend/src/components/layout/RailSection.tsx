import type { ReactNode } from 'react'

interface RailSectionProps {
  title: string
  meta?: ReactNode
  headerAction?: ReactNode
  children: ReactNode
  flex?: boolean
  noPadding?: boolean
}

/** Left-rail section with consistent header and body spacing. */
export default function RailSection({
  title, meta, headerAction, children, flex, noPadding,
}: RailSectionProps) {
  return (
    <section
      style={{
        display: 'flex',
        flexDirection: 'column',
        borderBottom: '1px solid var(--border)',
        flex: flex ? 1 : undefined,
        minHeight: flex ? 0 : undefined,
        overflow: flex ? 'hidden' : undefined,
      }}
    >
      <header
        style={{
          padding: '8px 12px',
          background: 'var(--surface2)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 10,
            letterSpacing: '0.14em',
            color: 'var(--text-dim)',
            textTransform: 'uppercase',
            fontWeight: 600,
          }}
        >
          {title}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {meta && (
            <span style={{ fontSize: 9, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
              {meta}
            </span>
          )}
          {headerAction}
        </span>
      </header>
      <div
        style={{
          padding: noPadding ? 0 : 12,
          flex: flex ? 1 : undefined,
          minHeight: flex ? 0 : undefined,
          overflow: flex ? 'hidden' : undefined,
          display: flex ? 'flex' : undefined,
          flexDirection: flex ? 'column' : undefined,
        }}
      >
        {children}
      </div>
    </section>
  )
}
