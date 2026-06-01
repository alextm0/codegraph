import type { PPREntityResult, GraphNode } from '../../types/api'

interface ResultsListProps {
  results: PPREntityResult[]
  onNodeSelect?: (node: GraphNode) => void
}

export default function ResultsList({ results, onNodeSelect }: ResultsListProps) {
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
          letterSpacing: '0.12em',
          color: 'var(--text-dim)',
          textTransform: 'uppercase',
          fontWeight: 600,
          flexShrink: 0,
        }}
      >
        Structural Ranking
      </div>

      {/* Column headers — simplified */}
      <div
        style={{
          padding: '8px 12px 6px',
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          fontSize: 8.5,
          letterSpacing: '0.14em',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          flexShrink: 0,
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span>Ranked Entities</span>
        <span style={{ color: 'var(--accent)' }}>Relevance</span>
      </div>

      {/* Rows */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {results.length === 0 ? (
          <div
            style={{
              padding: 20,
              fontSize: 11,
              color: 'var(--text-muted)',
              fontStyle: 'italic',
              letterSpacing: '0.02em',
            }}
          >
            // awaiting query results...
          </div>
        ) : (
          results.map((res) => {
            const fp = res.file_path
            const parts = fp.split('/')
            const fileName = parts.pop() ?? fp
            const dir = parts.join('/')

            const handleClick = () => {
              if (onNodeSelect) {
                onNodeSelect({
                  id: res.qualified_name,
                  label: res.label as any,
                  name: res.name,
                  file_path: fp,
                  ppr_score: res.score,
                  is_seed: false,
                  seed_weight: 0,
                  line_number: res.line_number,
                  line_end: res.line_end,
                })
              }
            }

            return (
              <div
                key={res.qualified_name}
                onClick={handleClick}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  borderBottom: `1px solid var(--border)`,
                  background: 'transparent',
                  cursor: 'pointer',
                  padding: '10px 12px',
                  transition: 'background 120ms',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'color-mix(in oklch, var(--surface2) 60%, transparent)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    gap: 12,
                    marginBottom: 2,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      minWidth: 0,
                    }}
                  >
                    <div
                      style={{
                        color: 'var(--text-muted)',
                        fontVariantNumeric: 'tabular-nums',
                        fontSize: 10,
                        width: 14,
                        textAlign: 'right',
                        flexShrink: 0,
                      }}
                    >
                      {res.rank}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                      <span
                        style={{
                          fontSize: 8,
                          fontWeight: 700,
                          padding: '1px 4px',
                          background: 'var(--surface2)',
                          color: 'var(--text-dim)',
                          borderRadius: 2,
                          textTransform: 'uppercase',
                          flexShrink: 0,
                        }}
                      >
                        {res.label[0]}
                      </span>
                      <div
                        style={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          color: 'var(--text)',
                          fontWeight: 600,
                          fontSize: 12,
                          letterSpacing: '0.01em',
                        }}
                      >
                        {res.name}
                      </div>
                    </div>
                  </div>
                  <div
                    style={{
                      color: 'var(--accent)',
                      fontSize: 10,
                      fontWeight: 600,
                      fontVariantNumeric: 'tabular-nums slashed-zero',
                      flexShrink: 0,
                    }}
                  >
                    {res.score.toFixed(4)}
                  </div>
                </div>

                <div
                  style={{
                    paddingLeft: 24,
                    fontSize: 9.5,
                    color: 'var(--text-muted)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={fp}
                >
                  {dir ? `${dir}/` : ''}<span style={{ color: 'var(--text-dim)' }}>{fileName}</span>
                </div>

                {res.path && (
                  <div
                    style={{
                      padding: '6px 0 0 24px',
                      fontSize: 9,
                      color: 'var(--text-dim)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      fontFamily: 'var(--font-mono)',
                      opacity: 0.8,
                    }}
                    title={res.path}
                  >
                    <span style={{ color: 'var(--accent)', opacity: 0.6 }}>↳</span> {res.path}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Footer */}
      {results.length > 0 && (
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
            <span style={{ color: 'var(--accent)' }}>◆</span> {results.length} entities ranked
          </span>
        </div>
      )}
    </div>
  )
}
