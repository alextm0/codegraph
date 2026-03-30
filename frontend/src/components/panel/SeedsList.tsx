import type { SeedInfo } from '../../types/api'

interface SeedsListProps {
  seeds: SeedInfo[]
  loading?: boolean
}

function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 4 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          style={{
            height: 10,
            marginBottom: 5,
            borderRadius: 'var(--radius-sm)',
            width: `${50 + (i % 3) * 18}%`,
            background: 'linear-gradient(90deg,var(--surface) 25%,var(--surface2) 50%,var(--surface) 75%)',
            backgroundSize: '800px 100%',
            animation: 'shimmer 1.4s infinite',
          }}
        />
      ))}
    </div>
  )
}

export default function SeedsList({ seeds, loading = false }: SeedsListProps) {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow)',
        padding: 12,
        flexShrink: 0,
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--text-dim)',
          marginBottom: 8,
        }}
      >
        Seeds ({loading ? '…' : seeds.length})
      </div>
      {loading ? (
        <ListSkeleton rows={4} />
      ) : seeds.length === 0 ? (
        <div style={{ color: 'var(--text-dim)', fontSize: 11 }}>No seeds yet.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {seeds.map((s, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 6px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--surface2)',
                minWidth: 0,
              }}
            >
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 600,
                  padding: '1px 4px',
                  borderRadius: 3,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  flexShrink: 0,
                  background: s.signal === 'entity'
                    ? 'rgba(99,102,241,0.2)'
                    : 'rgba(100,116,139,0.15)',
                  color: s.signal === 'entity' ? 'var(--accent2)' : 'var(--text-dim)',
                }}
              >
                {s.signal}
              </span>
              <span
                title={s.name}
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  color: 'var(--text)',
                  flex: 1,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  minWidth: 0,
                }}
              >
                {s.name}
              </span>
              <span
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  fontVariantNumeric: 'tabular-nums',
                  color: 'var(--text-dim)',
                  flexShrink: 0,
                }}
              >
                {s.weight.toFixed(3)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
