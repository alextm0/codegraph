import type { PPRFileResult, BM25FileResult, GraphNode } from '../../types/api'

interface ResultsListProps {
  results: PPRFileResult[]
  bm25Results: BM25FileResult[]
  onNodeSelect?: (node: GraphNode) => void
}

export default function ResultsList({ results, bm25Results, onNodeSelect }: ResultsListProps) {
  const pprMap  = Object.fromEntries(results.map(r => [r.file_path, r]))
  const bm25Map = Object.fromEntries(bm25Results.map(r => [r.file_path, r.rank]))
  const allFiles = [
    ...new Set([...results.map(r => r.file_path), ...bm25Results.map(r => r.file_path)]),
  ]

  const iouCount = allFiles.filter(fp => fp in pprMap && fp in bm25Map).length
  const iou = allFiles.length > 0
    ? (iouCount / allFiles.length).toFixed(2)
    : '—'

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
        background: 'var(--surface)',
        borderLeft: '1px solid var(--border)',
      }}
    >
      {/* Section header */}
      <div
        style={{
          padding: '8px 12px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface2)',
          fontSize: 10,
          letterSpacing: '0.16em',
          color: 'var(--text-dim)',
          textTransform: 'uppercase',
          flexShrink: 0,
        }}
      >
        ▸ ranked.results / bm25.compare
      </div>

      {/* Column headers */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '28px 1fr 1fr',
          padding: '6px 12px',
          gap: 8,
          background: 'var(--bg)',
          borderBottom: '1px solid var(--border)',
          fontSize: 9,
          letterSpacing: '0.14em',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          flexShrink: 0,
        }}
      >
        <div>#</div>
        <div style={{ color: 'var(--accent)' }}>codegraph[ppr]</div>
        <div>bm25[lex]</div>
      </div>

      {/* Rows */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {allFiles.length === 0 ? (
          <div
            style={{
              padding: 16,
              fontSize: 11,
              color: 'var(--text-muted)',
              fontStyle: 'italic',
            }}
          >
            // awaiting query
          </div>
        ) : (
          allFiles.slice(0, 30).map((fp, i) => {
            const pprRes = pprMap[fp]
            const inPpr  = !!pprRes
            const inBm25 = fp in bm25Map
            const isWin  = inPpr && !inBm25
            const isMiss = !inPpr && inBm25
            const short  = fp.split('/').pop() ?? fp

            const handleClick = () => {
              if (onNodeSelect) {
                onNodeSelect({
                  id: fp,
                  label: 'File',
                  name: short,
                  file_path: fp,
                  ppr_score: pprRes ? pprRes.score : 0,
                  is_seed: false,
                  seed_weight: 0,
                })
              }
            }

            return (
              <div
                key={fp}
                onClick={handleClick}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  borderBottom: `1px dashed var(--border)`,
                  background: isWin
                    ? 'var(--accent-soft)'
                    : i % 2 === 0
                    ? 'transparent'
                    : 'var(--surface2)',
                  cursor: 'pointer',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'color-mix(in oklch, var(--accent) 15%, transparent)' }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = isWin
                    ? 'var(--accent-soft)'
                    : i % 2 === 0
                    ? 'transparent'
                    : 'var(--surface2)'
                }}
              >
                <div
                  title={fp}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '28px 1fr 1fr',
                    gap: 8,
                    padding: '6px 12px',
                    fontSize: 10.5,
                    alignItems: 'center',
                  }}
                >
                  <div
                    style={{
                      color: isWin ? 'var(--accent)' : isMiss ? 'var(--text-dim)' : 'var(--text-muted)',
                      fontVariantNumeric: 'tabular-nums',
                      fontSize: 11,
                    }}
                  >
                    {isWin ? '◆' : isMiss ? '○' : '·'}
                  </div>
                  <div
                    style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      color: inPpr ? (isWin ? 'var(--accent)' : 'var(--text)') : 'var(--text-muted)',
                    }}
                  >
                    {inPpr ? (
                      <>
                        <span style={{ color: 'var(--text-muted)' }}>
                          {String(pprRes.rank).padStart(2, '0')}{' '}
                        </span>
                        {short}
                      </>
                    ) : '—'}
                  </div>
                  <div
                    style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      color: inBm25 ? (isMiss ? 'var(--text-dim)' : 'var(--text)') : 'var(--text-muted)',
                    }}
                  >
                    {inBm25 ? (
                      <>
                        <span style={{ color: 'var(--text-muted)' }}>
                          {String(bm25Map[fp]).padStart(2, '0')}{' '}
                        </span>
                        {short}
                      </>
                    ) : '—'}
                  </div>
                </div>
                {inPpr && pprRes.path && (
                  <div
                    style={{
                      padding: '0 12px 6px 48px',
                      fontSize: 9,
                      color: 'var(--text-dim)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      fontFamily: 'var(--font-mono)',
                    }}
                    title={pprRes.path}
                  >
                    <span style={{ color: 'var(--accent)', opacity: 0.7 }}>↳</span> {pprRes.path}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Footer */}
      {allFiles.length > 0 && (
        <div
          style={{
            padding: '8px 12px',
            borderTop: '1px solid var(--border)',
            background: 'var(--surface2)',
            fontSize: 9,
            color: 'var(--text-dim)',
            letterSpacing: '0.06em',
            display: 'flex',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <span>
            <span style={{ color: 'var(--accent)' }}>◆</span> ppr-only ·{' '}
            <span style={{ color: 'var(--text-dim)' }}>○</span> bm25-only
          </span>
          <span>iou · {iou}</span>
        </div>
      )}
    </div>
  )
}
