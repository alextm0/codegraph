import type { PPRFileResult, BM25FileResult } from '../../types/api'

interface ResultsListProps {
  results: PPRFileResult[]
  bm25Results: BM25FileResult[]
  loading?: boolean
}

function ListSkeleton({ rows = 5 }: { rows?: number }) {
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

export default function ResultsList({ results, bm25Results, loading = false }: ResultsListProps) {
  const pprMap: Record<string, number> = Object.fromEntries(
    results.map((r) => [r.file_path, r.rank]),
  )
  const bm25Map: Record<string, number> = Object.fromEntries(
    bm25Results.map((r) => [r.file_path, r.rank]),
  )
  const allFiles = [
    ...new Set([...results.map((r) => r.file_path), ...bm25Results.map((r) => r.file_path)]),
  ]

  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow)',
        padding: 12,
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
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
        BM25 vs CodeGraph
      </div>
      {loading ? (
        <ListSkeleton rows={7} />
      ) : allFiles.length === 0 ? (
        <div style={{ color: 'var(--text-dim)', fontSize: 11 }}>Run a query to compare.</div>
      ) : (
        <>
          {/* Header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '20px 1fr 1fr',
              gap: 4,
              padding: '0 4px 4px',
              borderBottom: '1px solid var(--border)',
              marginBottom: 4,
            }}
          >
            <span />
            <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)' }}>
              CodeGraph
            </span>
            <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)' }}>
              BM25
            </span>
          </div>
          {/* Scrollable rows */}
          <div style={{ maxHeight: 280, overflowY: 'auto', overflowX: 'hidden' }}>
            {allFiles.slice(0, 20).map((fp) => {
              const inPpr = fp in pprMap
              const inBm25 = fp in bm25Map
              const isWin = inPpr && !inBm25
              const isMiss = !inPpr && inBm25
              const parts = fp.split('/')
              const short = parts[parts.length - 1] ?? fp

              return (
                <div
                  key={fp}
                  title={fp}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '20px 1fr 1fr',
                    gap: 4,
                    alignItems: 'center',
                    padding: '2px 4px',
                    borderRadius: 3,
                    background: isWin
                      ? 'rgba(250,204,21,0.08)'
                      : isMiss
                      ? 'rgba(248,113,113,0.06)'
                      : 'transparent',
                  }}
                >
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-dim)', textAlign: 'right' }}>
                    {isWin ? '★' : ''}
                  </span>
                  {inPpr ? (
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: isWin ? 'var(--yellow)' : 'var(--text)' }}>
                      #{pprMap[fp]} {short}
                    </span>
                  ) : (
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--border)' }}>—</span>
                  )}
                  {inBm25 ? (
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: isMiss ? 'var(--red)' : 'var(--text)' }}>
                      #{bm25Map[fp]} {short}
                    </span>
                  ) : (
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--border)' }}>—</span>
                  )}
                </div>
              )
            })}
          </div>
          <div style={{ fontSize: 9, color: 'var(--text-dim)', marginTop: 6 }}>
            ★ = PPR win (not in BM25)
          </div>
        </>
      )}
    </div>
  )
}
