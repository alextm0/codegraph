import { useCallback, type KeyboardEvent } from 'react'

interface QueryInputProps {
  task: string
  setTask: (task: string) => void
  topK: number
  setTopK: (topK: number) => void
  loading: boolean
  error: string | null
  onRun: () => void
}

export default function QueryInput({
  task, setTask, topK, setTopK, loading, error, onRun,
}: QueryInputProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') onRun()
    },
    [onRun],
  )

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
        Query
      </div>
      <textarea
        value={task}
        onChange={(e) => setTask(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Describe the task… (Ctrl+Enter)"
        rows={4}
        style={{
          width: '100%',
          background: 'var(--surface2)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text)',
          fontFamily: 'var(--font)',
          fontSize: 13,
          padding: 8,
          resize: 'none',
          minHeight: 72,
          outline: 'none',
          transition: 'border-color 180ms ease',
        }}
        onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
        onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
      />
      {error && (
        <div
          style={{
            background: 'rgba(248,113,113,0.1)',
            border: '1px solid rgba(248,113,113,0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '8px 12px',
            color: 'var(--red)',
            fontSize: 11,
            marginTop: 6,
            wordBreak: 'break-word',
          }}
        >
          {error}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
        <button
          onClick={onRun}
          disabled={loading || !task.trim()}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 34,
            padding: '0 16px',
            background: 'var(--accent)',
            color: '#fff',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontFamily: 'var(--font)',
            fontSize: 13,
            fontWeight: 500,
            cursor: loading || !task.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !task.trim() ? 0.4 : 1,
            minWidth: 44,
            transition: 'opacity 150ms, transform 120ms',
          }}
        >
          {loading ? '⟳' : 'Run'}
        </button>
      </div>
      <details style={{ marginTop: 8 }}>
        <summary
          style={{
            cursor: 'pointer',
            color: 'var(--text-dim)',
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.05em',
            listStyle: 'none',
          }}
        >
          ▸ Advanced
        </summary>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
          <label style={{ color: 'var(--text-dim)', flex: 1, fontSize: 11 }}>top_k</label>
          <input
            type="range"
            min={5}
            max={30}
            step={1}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            style={{ flex: 2, accentColor: 'var(--accent)' }}
          />
          <span
            style={{
              fontVariantNumeric: 'tabular-nums',
              fontFamily: 'var(--mono)',
              color: 'var(--text-dim)',
              width: 24,
              textAlign: 'right',
              fontSize: 11,
            }}
          >
            {topK}
          </span>
        </div>
      </details>
    </div>
  )
}
