import { useState, useCallback, type KeyboardEvent } from 'react'
import type { SeedInfo, GraphNode } from '../../types/api'

interface LeftRailProps {
  task: string
  setTask: (t: string) => void
  topK: number
  setTopK: (k: number) => void
  loading: boolean
  error: string | null
  onRun: () => void
  seeds: SeedInfo[]
  hasRun: boolean
  onNodeSelect?: (node: GraphNode) => void
}

export default function LeftRail({
  task, setTask, topK, setTopK,
  loading, error, onRun,
  seeds, hasRun,
  onNodeSelect,
}: LeftRailProps) {
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)

  const handleRun = useCallback(() => {
    if (task.trim()) {
      setHistory(prev => {
        const filtered = prev.filter(t => t !== task.trim())
        return [task.trim(), ...filtered].slice(0, 50)
      })
    }
    setHistoryIndex(-1)
    onRun()
  }, [task, onRun])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        handleRun()
      } else if (e.key === 'ArrowUp' && e.currentTarget.selectionStart === 0 && e.currentTarget.selectionEnd === 0) {
        e.preventDefault()
        const nextIdx = Math.min(historyIndex + 1, history.length - 1)
        if (nextIdx >= 0) {
          setHistoryIndex(nextIdx)
          setTask(history[nextIdx])
        }
      } else if (e.key === 'ArrowDown' && e.currentTarget.selectionStart === e.currentTarget.value.length) {
        e.preventDefault()
        const nextIdx = historyIndex - 1
        if (nextIdx >= 0) {
          setHistoryIndex(nextIdx)
          setTask(history[nextIdx])
        } else if (nextIdx === -1) {
          setHistoryIndex(-1)
          setTask('')
        }
      }
    },
    [handleRun, history, historyIndex, setTask]
  )

  const entitySeeds = seeds.filter(s => s.signal === 'entity')
  const totalW      = seeds.reduce((a, s) => a + s.weight, 0)
  const entityPct   = totalW > 0
    ? (entitySeeds.reduce((a, s) => a + s.weight, 0) / totalW) * 100
    : 0
  const maxWeight   = seeds.length > 0 ? Math.max(...seeds.map(s => s.weight)) : 1

  return (
    <div
      style={{
        borderRight: '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        userSelect: 'none',
        height: '100%',
      }}
    >
      {/* ▸ task.input header */}
      <SectionHeader
        label="▸ task.input"
        right={<span style={{ fontSize: 9, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{task.length} ch</span>}
      />

      {/* Textarea */}
      <div style={{ padding: 12, flexShrink: 0 }}>
        <textarea
          value={task}
          onChange={e => setTask(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={5}
          placeholder="// describe the task..."
          style={{
            width: '100%',
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            color: 'var(--text)',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            padding: 10,
            resize: 'none',
            outline: 'none',
            lineHeight: 1.5,
            transition: 'border-color 150ms',
            userSelect: 'text',
          }}
          onFocus={e => { e.currentTarget.style.borderColor = 'var(--accent)' }}
          onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
        />

        {error && (
          <div
            style={{
              marginTop: 6,
              padding: '6px 10px',
              background: 'oklch(0.22 0.05 25)',
              border: '1px solid oklch(0.40 0.10 25)',
              fontSize: 10,
              color: 'oklch(0.80 0.14 25)',
              letterSpacing: '0.04em',
              wordBreak: 'break-word',
            }}
          >
            {error}
          </div>
        )}

        {/* Controls row */}
        <div
          style={{
            marginTop: 8,
            display: 'grid',
            gridTemplateColumns: 'auto 1fr auto auto',
            gap: 8,
            alignItems: 'center',
          }}
        >
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>top_k</span>
          <input
            type="range"
            min={5}
            max={30}
            step={1}
            value={topK}
            onChange={e => setTopK(Number(e.target.value))}
            style={{ accentColor: 'var(--accent)' }}
          />
          <span
            style={{
              fontSize: 10,
              color: 'var(--text)',
              fontVariantNumeric: 'tabular-nums',
              minWidth: 18,
              textAlign: 'right',
            }}
          >
            {topK}
          </span>

          <ExecButton loading={loading} disabled={!task.trim()} onClick={handleRun} />
        </div>

        <div
          style={{
            marginTop: 6,
            fontSize: 9,
            color: 'var(--text-muted)',
            letterSpacing: '0.04em',
          }}
        >
          ⌘↵ run · ↑/↓ history
        </div>
      </div>

      {/* ▸ seed.signals header */}
      <div
        style={{
          padding: '10px 12px 8px',
          borderTop: '1px solid var(--border)',
          background: 'var(--surface2)',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: 8,
          }}
        >
          <span
            style={{
              fontSize: 10,
              letterSpacing: '0.16em',
              color: 'var(--text-dim)',
              textTransform: 'uppercase',
            }}
          >
            ▸ seed.signals
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
            n={seeds.length} · Σw={totalW.toFixed(2)}
          </span>
        </div>

        {/* Entity/BM25 distribution bar */}
        {hasRun && seeds.length > 0 && (
          <div>
            <div
              style={{
                height: 4,
                background: 'var(--border)',
                display: 'flex',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${entityPct}%`,
                  background: 'var(--accent)',
                  transition: 'width 600ms cubic-bezier(.2,.8,.2,1)',
                }}
              />
              <div style={{ flex: 1, background: 'var(--border-strong)' }} />
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginTop: 4,
                fontSize: 9,
              }}
            >
              <span style={{ color: 'var(--accent)', letterSpacing: '0.08em' }}>
                ◆ entity {entityPct.toFixed(0)}%
              </span>
              <span style={{ color: 'var(--text-dim)', letterSpacing: '0.08em' }}>
                bm25 {(100 - entityPct).toFixed(0)}% ◇
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Column headers */}
      <div
        style={{
          padding: '0 12px 6px',
          background: 'var(--surface2)',
          borderBottom: '1px solid var(--border)',
          display: 'grid',
          gridTemplateColumns: '14px 1fr 64px',
          gap: 8,
          alignItems: 'center',
          fontSize: 8.5,
          letterSpacing: '0.14em',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          flexShrink: 0,
        }}
      >
        <span>#</span>
        <span>signal / source</span>
        <span style={{ textAlign: 'right' }}>weight</span>
      </div>

      {/* Seed rows */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {!hasRun ? (
          <div
            style={{
              padding: 16,
              fontSize: 11,
              color: 'var(--text-muted)',
              fontStyle: 'italic',
              letterSpacing: '0.02em',
            }}
          >
            // awaiting query — seeds derive from entity match + bm25 fallback
          </div>
        ) : seeds.length === 0 ? (
          <div style={{ padding: 16, fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            // no seeds found
          </div>
        ) : (
          <>
            {seeds.map((seed, i) => (
              <SeedRow key={`${seed.name}-${i}`} seed={seed} idx={i} max={maxWeight} onNodeSelect={onNodeSelect} />
            ))}
            {/* Footnote */}
            <div
              style={{
                padding: '10px 12px',
                fontSize: 9,
                color: 'var(--text-muted)',
                letterSpacing: '0.04em',
                lineHeight: 1.5,
              }}
            >
              <div style={{ marginBottom: 3 }}>
                <span style={{ color: 'var(--accent)' }}>◆ entity</span> — exact name match in graph
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>◇ bm25</span> — lexical fallback
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

/* ── Section header ──────────────────────────────────────── */
function SectionHeader({ label, right }: { label: string; right?: React.ReactNode }) {
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
      }}
    >
      <span
        style={{
          fontSize: 10,
          letterSpacing: '0.16em',
          color: 'var(--text-dim)',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </span>
      {right}
    </div>
  )
}

/* ── Seed row ────────────────────────────────────────────── */
function SeedRow({ seed, idx, max, onNodeSelect }: { seed: SeedInfo; idx: number; max: number; onNodeSelect?: (node: GraphNode) => void }) {
  const pct = (seed.weight / max) * 100
  const isEntity = seed.signal === 'entity'
  const accentColor = isEntity ? 'var(--accent)' : 'var(--text-dim)'

  const handleClick = () => {
    if (onNodeSelect) {
      onNodeSelect({
        id: seed.name,
        name: seed.name.split('::').pop() || seed.name,
        file_path: '',
        label: 'Function',
        ppr_score: 0,
        is_seed: true,
        seed_weight: seed.weight,
      })
    }
  }

  return (
    <div
      onClick={handleClick}
      style={{
        position: 'relative',
        padding: '8px 12px 9px',
        display: 'grid',
        gridTemplateColumns: '14px 1fr 64px',
        gap: 8,
        alignItems: 'center',
        borderBottom: '1px solid var(--border)',
        background: isEntity ? 'color-mix(in oklch, var(--accent-soft) 40%, transparent)' : 'transparent',
        cursor: 'pointer',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'color-mix(in oklch, var(--accent) 15%, transparent)' }}
      onMouseLeave={e => {
        e.currentTarget.style.background = isEntity
          ? 'color-mix(in oklch, var(--accent-soft) 40%, transparent)'
          : 'transparent'
      }}
    >
      {/* Index + glyph */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
        <span
          style={{
            fontSize: 8.5,
            color: 'var(--text-muted)',
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: '0.04em',
          }}
        >
          {String(idx + 1).padStart(2, '0')}
        </span>
        <span style={{ fontSize: 9, color: accentColor, lineHeight: 1 }}>
          {isEntity ? '◆' : '◇'}
        </span>
      </div>

      {/* Name + signal type */}
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 12,
            color: 'var(--text)',
            fontWeight: 500,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            letterSpacing: '0.005em',
          }}
        >
          {seed.name}
        </div>
        <div
          style={{
            marginTop: 2,
            fontSize: 8.5,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: accentColor,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span>{isEntity ? 'entity match' : 'lexical bm25'}</span>
        </div>
      </div>

      {/* Weight + spark bar with tick marks */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
        <span
          style={{
            fontSize: 11,
            color: accentColor,
            fontWeight: 600,
            fontVariantNumeric: 'tabular-nums slashed-zero',
          }}
        >
          {seed.weight.toFixed(3)}
        </span>
        <div
          style={{
            width: 60,
            height: 6,
            background: 'var(--border)',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 0, bottom: 0, left: 0,
              width: `${pct}%`,
              background: accentColor,
              transition: 'width 700ms cubic-bezier(.2,.8,.2,1)',
            }}
          />
          {/* Tick marks at 25/50/75 */}
          {[25, 50, 75].map(tick => (
            <div
              key={tick}
              style={{
                position: 'absolute',
                top: 0, bottom: 0,
                left: `${tick}%`,
                width: 1,
                background: 'var(--bg)',
                opacity: 0.6,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

/* ── Exec button ─────────────────────────────────────────── */
function ExecButton({ loading, disabled, onClick }: {
  loading: boolean
  disabled: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      style={{
        background: loading ? 'var(--accent-soft)' : 'var(--accent)',
        color: loading ? 'var(--accent-ink)' : 'var(--bg)',
        border: '1px solid var(--accent)',
        padding: '5px 14px',
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
        fontWeight: 600,
        cursor: loading || disabled ? 'not-allowed' : 'pointer',
        opacity: disabled && !loading ? 0.4 : 1,
        transition: 'all 150ms',
        whiteSpace: 'nowrap',
      }}
    >
      {loading ? '⟳ exec' : '▶ exec'}
    </button>
  )
}
