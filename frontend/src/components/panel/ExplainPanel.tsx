import type { PPREntityResult, SeedInfo } from '../../types/api'

interface ExplainPanelProps {
  results: PPREntityResult[]
  seeds: SeedInfo[]
  dampingFactor?: number
}

export default function ExplainPanel({ results, seeds, dampingFactor = 0.70 }: ExplainPanelProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', background: 'var(--surface2)', flexShrink: 0 }}>
        <div style={{ fontSize: 10, letterSpacing: '0.12em', color: 'var(--text-dim)', textTransform: 'uppercase' }}>
          PPR explain · α={dampingFactor.toFixed(2)}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {seeds.length > 0 && (
          <section style={{ padding: 12, borderBottom: '1px dashed var(--border)' }}>
            <div style={label}>Seeds ({seeds.length})</div>
            {seeds.map((s, i) => (
              <div key={`${s.id}-${i}`} style={{ display: 'grid', gridTemplateColumns: '24px 1fr auto', gap: 8, padding: '4px 0', fontSize: 10 }}>
                <span style={{ color: 'var(--text-muted)' }}>{String(i + 1).padStart(2, '0')}</span>
                <span style={{ color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.name}>
                  {s.name}
                </span>
                <span style={{ color: s.signal === 'entity' ? 'var(--accent)' : 'var(--seed)', fontVariantNumeric: 'tabular-nums' }}>
                  {s.weight.toFixed(3)}
                </span>
              </div>
            ))}
          </section>
        )}

        {results.map(r => (
          <section key={r.qualified_name} style={{ padding: 12, borderBottom: '1px dashed var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>{r.name}</span>
              <span style={{ fontSize: 10, color: 'var(--accent)', fontVariantNumeric: 'tabular-nums' }}>{r.score.toFixed(5)}</span>
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 6 }}>{r.file_path}</div>
            {r.path && (
              <div style={{ fontSize: 10, color: 'var(--text-dim)', lineHeight: 1.5, padding: 8, background: 'var(--bg)', border: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--accent)', marginRight: 6 }}>path</span>
                {r.path}
              </div>
            )}
            {r.contribution && (
              <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 4 }}>
                contribution · {r.contribution}
              </div>
            )}
          </section>
        ))}

        {results.length === 0 && seeds.length === 0 && (
          <div style={{ padding: 16, fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            // run a query to see seed selection and reasoning paths
          </div>
        )}
      </div>
    </div>
  )
}

const label: React.CSSProperties = {
  fontSize: 9,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: 'var(--text-muted)',
  marginBottom: 8,
}
