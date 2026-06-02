import type { PPREntityResult, SeedInfo, GraphNode } from '../../types/api'
import { oneLineWhy, seedKind, shortName } from './explainFormat'

interface ExplainPanelProps {
  results: PPREntityResult[]
  seeds: SeedInfo[]
  onNodeSelect?: (node: GraphNode) => void
}

export default function ExplainPanel({ results, seeds, onNodeSelect }: ExplainPanelProps) {
  return (
    <div style={{ height: '100%', overflowY: 'auto', fontSize: 11, color: 'var(--text)' }}>
      {seeds.length > 0 && (
        <section style={section}>
          <div style={label}>Seeds</div>
          {seeds.map((s, i) => (
            <div key={`${s.id}-${i}`} style={seedRow}>
              <span style={name}>{shortName(s.name)}</span>
              <span style={meta}>{seedKind(s.signal)}</span>
            </div>
          ))}
        </section>
      )}

      {results.length === 0 ? (
        <p style={empty}>Run a query to see why each result ranked.</p>
      ) : (
        <section style={section}>
          <div style={label}>Why ranked</div>
          {results.map(r => (
            <ResultRow
              key={r.qualified_name}
              result={r}
              onSelect={onNodeSelect ? () => onNodeSelect(toGraphNode(r)) : undefined}
            />
          ))}
        </section>
      )}
    </div>
  )
}

function ResultRow({
  result,
  onSelect,
}: {
  result: PPREntityResult
  onSelect?: () => void
}) {
  return (
    <div
      style={{
        ...row,
        cursor: onSelect ? 'pointer' : undefined,
      }}
      onClick={onSelect}
      onKeyDown={onSelect ? e => { if (e.key === 'Enter') onSelect() } : undefined}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
    >
      <div style={titleRow}>
        <span style={rank}>#{result.rank}</span>
        <span style={name}>{result.name}</span>
      </div>
      <div style={file} title={result.file_path}>{result.file_path}</div>
      <div style={why}>{oneLineWhy(result)}</div>
    </div>
  )
}

function toGraphNode(r: PPREntityResult): GraphNode {
  return {
    id: r.qualified_name,
    name: r.name,
    label: r.label as GraphNode['label'],
    file_path: r.file_path,
    ppr_score: r.score,
    is_seed: r.path === 'direct seed',
    seed_weight: 0,
    reasoning_path: r.path_ids,
    line_number: r.line_number,
    line_end: r.line_end,
  }
}

const section: React.CSSProperties = {
  padding: '10px 12px',
  borderBottom: '1px solid var(--border)',
}

const label: React.CSSProperties = {
  fontSize: 10,
  color: 'var(--text-muted)',
  marginBottom: 8,
}

const seedRow: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: 8,
  padding: '3px 0',
}

const row: React.CSSProperties = {
  padding: '8px 0',
  borderBottom: '1px solid color-mix(in oklch, var(--border) 55%, transparent)',
}

const titleRow: React.CSSProperties = {
  display: 'flex',
  alignItems: 'baseline',
  gap: 6,
}

const rank: React.CSSProperties = {
  fontSize: 10,
  color: 'var(--text-muted)',
  fontFamily: 'var(--font-mono)',
  flexShrink: 0,
}

const name: React.CSSProperties = {
  fontWeight: 500,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const file: React.CSSProperties = {
  fontSize: 10,
  color: 'var(--text-muted)',
  marginTop: 2,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const why: React.CSSProperties = {
  fontSize: 10,
  color: 'var(--text-dim)',
  marginTop: 4,
  lineHeight: 1.45,
}

const meta: React.CSSProperties = {
  fontSize: 10,
  color: 'var(--text-muted)',
  flexShrink: 0,
}

const empty: React.CSSProperties = {
  padding: 16,
  color: 'var(--text-muted)',
  margin: 0,
}
