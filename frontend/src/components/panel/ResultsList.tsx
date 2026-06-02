import { useMemo, useState } from 'react'
import type { PPREntityResult, BM25FileResult, GraphNode } from '../../types/api'

interface ResultsListProps {
  results: PPREntityResult[]
  bm25Results?: BM25FileResult[]
  onNodeSelect?: (node: GraphNode) => void
}

type ViewMode = 'ppr' | 'bm25' | 'compare'

export default function ResultsList({
  results,
  bm25Results = [],
  onNodeSelect,
}: ResultsListProps) {
  const [mode, setMode] = useState<ViewMode>('ppr')

  const bm25RankByFile = useMemo(
    () => new Map(bm25Results.map((r) => [r.file_path, r.rank])),
    [bm25Results],
  )
  const pprFiles = useMemo(() => new Set(results.map((r) => r.file_path)), [results])
  const bm25OnlyFiles = useMemo(
    () => bm25Results.filter((r) => !pprFiles.has(r.file_path)).map((r) => r.file_path),
    [bm25Results, pprFiles],
  )
  const pprOnlyFiles = useMemo(
    () => results.filter((r) => !bm25RankByFile.has(r.file_path)).map((r) => r.file_path),
    [results, bm25RankByFile],
  )

  const headerStyle = {
    padding: '8px 12px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--surface2)',
    fontSize: 10,
    letterSpacing: '0.12em',
    color: 'var(--text-dim)',
    textTransform: 'uppercase' as const,
    fontWeight: 600,
    flexShrink: 0,
  }

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
      <div style={headerStyle}>
        <div style={{ marginBottom: 6 }}>Retrieval comparison</div>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['ppr', 'bm25', 'compare'] as ViewMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              style={{
                flex: 1,
                padding: '4px 6px',
                fontSize: 9,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                border: `1px solid ${mode === m ? 'var(--accent)' : 'var(--border)'}`,
                background: mode === m ? 'color-mix(in oklch, var(--accent) 15%, transparent)' : 'transparent',
                color: mode === m ? 'var(--accent)' : 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              {m === 'ppr' ? 'Structural' : m === 'bm25' ? 'Lexical' : 'Delta'}
            </button>
          ))}
        </div>
      </div>

      {mode === 'compare' && (
        <div style={{ padding: '8px 12px', fontSize: 10, color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
          <div><span style={{ color: 'var(--accent)' }}>+{pprOnlyFiles.length}</span> files only PPR surfaced</div>
          <div><span style={{ color: 'var(--text-dim)' }}>−{bm25OnlyFiles.length}</span> files only BM25 surfaced</div>
        </div>
      )}

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
        <span>{mode === 'bm25' ? 'BM25 files' : 'Ranked entities'}</span>
        <span style={{ color: 'var(--accent)' }}>{mode === 'bm25' ? 'Lexical' : 'PPR score'}</span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {mode === 'bm25' ? (
          bm25Results.length === 0 ? (
            <EmptyHint />
          ) : (
            bm25Results.map((row) => (
              <Bm25Row
                key={row.file_path}
                row={row}
                highlight={!pprFiles.has(row.file_path)}
              />
            ))
          )
        ) : results.length === 0 ? (
          <EmptyHint />
        ) : (
          results.map((res) => (
            <PprRow
              key={res.qualified_name}
              res={res}
              bm25Rank={bm25RankByFile.get(res.file_path)}
              highlightPprOnly={mode === 'compare' && !bm25RankByFile.has(res.file_path)}
              onNodeSelect={onNodeSelect}
            />
          ))
        )}
      </div>

      {(results.length > 0 || bm25Results.length > 0) && (
        <div
          style={{
            padding: '8px 12px',
            borderTop: '1px solid var(--border)',
            background: 'var(--surface2)',
            fontSize: 9,
            color: 'var(--text-dim)',
            flexShrink: 0,
          }}
        >
          PPR: {results.length} · BM25: {bm25Results.length}
        </div>
      )}
    </div>
  )
}

function EmptyHint() {
  return (
    <div style={{ padding: 20, fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
      Run a query to compare structural (PPR) vs lexical (BM25) rankings.
    </div>
  )
}

function Bm25Row({ row, highlight }: { row: BM25FileResult; highlight: boolean }) {
  return (
    <div
      style={{
        padding: '10px 12px',
        borderBottom: '1px solid var(--border)',
        background: highlight ? 'color-mix(in oklch, var(--accent) 8%, transparent)' : 'transparent',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
        <span style={{ color: 'var(--text)' }}>{row.rank}. {row.file_path}</span>
        {highlight && <span style={{ fontSize: 9, color: 'var(--accent)' }}>BM25 only</span>}
      </div>
    </div>
  )
}

function PprRow({
  res,
  bm25Rank,
  highlightPprOnly,
  onNodeSelect,
}: {
  res: PPREntityResult
  bm25Rank?: number
  highlightPprOnly: boolean
  onNodeSelect?: (node: GraphNode) => void
}) {
  const fp = res.file_path
  const parts = fp.split('/')
  const fileName = parts.pop() ?? fp
  const dir = parts.join('/')

  const handleClick = () => {
    onNodeSelect?.({
      id: res.qualified_name,
      label: res.label as GraphNode['label'],
      name: res.name,
      file_path: fp,
      ppr_score: res.score,
      is_seed: false,
      seed_weight: 0,
      line_number: res.line_number,
      line_end: res.line_end,
      reasoning_path: res.path_ids,
    })
  }

  return (
    <div
      onClick={handleClick}
      style={{
        padding: '10px 12px',
        borderBottom: '1px solid var(--border)',
        cursor: 'pointer',
        background: highlightPprOnly
          ? 'color-mix(in oklch, var(--accent) 10%, transparent)'
          : 'transparent',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ fontWeight: 600, fontSize: 12 }}>{res.rank}. {res.name}</span>
        <span style={{ color: 'var(--accent)', fontSize: 10 }}>{res.score.toFixed(4)}</span>
      </div>
      <div style={{ fontSize: 9.5, color: 'var(--text-muted)' }}>
        {dir ? `${dir}/` : ''}{fileName}
      </div>
      {bm25Rank !== undefined && (
        <div style={{ fontSize: 9, color: 'var(--text-dim)', marginTop: 4 }}>
          BM25 rank: {bm25Rank}
          {bm25Rank > res.rank && (
            <span style={{ color: 'var(--accent)', marginLeft: 6 }}>↑ structural boost</span>
          )}
        </div>
      )}
      {highlightPprOnly && (
        <div style={{ fontSize: 9, color: 'var(--accent)', marginTop: 4 }}>PPR only — missed by BM25</div>
      )}
      {res.path && (
        <div style={{ fontSize: 9, color: 'var(--text-dim)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
          ↳ {res.path}
        </div>
      )}
    </div>
  )
}
