import { useState } from 'react'
import { rebuildProject, initializeProject, ProjectHistoryItem } from '../../api/client'

interface ProjectSettingsModalProps {
  onClose: () => void
  history?: ProjectHistoryItem[]
  onIndexed?: () => void
}

export default function ProjectSettingsModal({ onClose, history = [], onIndexed }: ProjectSettingsModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const target = (e.currentTarget.elements.namedItem('target') as HTMLInputElement).value
    handleSwitch(target)
  }

  const handleSwitch = async (target: string) => {
    if (!target.trim()) return

    setLoading(true)
    setError(null)
    
    try {
      await initializeProject(target)
      onIndexed?.()
      onClose()
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div 
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'color-mix(in oklch, var(--bg) 80%, transparent)',
        backdropFilter: 'blur(4px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div 
        style={{
          background: 'var(--surface2)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          width: 440,
          boxShadow: 'var(--shadow)',
          overflow: 'hidden'
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: 13, color: 'var(--text)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Switch Project</h2>
          <button 
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 11 }}
          >
            [ESC]
          </button>
        </div>
        
        <div style={{ padding: 20 }}>
          {history.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>Previous Projects</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {history.map((proj, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSwitch(proj.url || proj.path)}
                    disabled={loading}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 12px',
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                      borderRadius: 4,
                      cursor: loading ? 'wait' : 'pointer',
                      textAlign: 'left',
                      transition: 'border-color 120ms'
                    }}
                    onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                    onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>{proj.name}</span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{proj.url || proj.path}</span>
                    </div>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>→</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <h3 style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>Index New Repository</h3>
          <form onSubmit={handleSubmit}>
            <input 
              name="target"
              placeholder="e.g., /Users/me/project or https://github.com/user/repo"
              autoFocus
              disabled={loading}
              style={{ 
                width: '100%', 
                padding: '10px 12px', 
                background: 'var(--surface)', 
                border: '1px solid var(--border)', 
                color: 'var(--text)', 
                marginBottom: 16, 
                fontFamily: 'var(--font-mono)', 
                fontSize: 12,
                borderRadius: 4
              }}
            />
            
            {error && (
              <div style={{ color: 'var(--node-function)', fontSize: 11, marginBottom: 16, padding: '8px 12px', background: 'color-mix(in srgb, var(--node-function) 10%, transparent)', border: '1px solid var(--node-function)', borderRadius: 4 }}>
                {error}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={async () => {
                  if (!window.confirm('Rebuild the current project graph?')) return
                  setLoading(true)
                  setError(null)
                  try {
                    await rebuildProject()
                    onIndexed?.()
                    onClose()
                  } catch (err) {
                    setError(String(err))
                  } finally {
                    setLoading(false)
                  }
                }}
                disabled={loading}
                style={{ padding: '8px 16px', background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', fontSize: 11 }}
              >
                Rebuild current
              </button>
              <button 
                type="button" 
                onClick={onClose}
                disabled={loading}
                style={{ padding: '8px 16px', background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', fontSize: 11, fontWeight: 500 }}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                disabled={loading}
                style={{ padding: '8px 16px', background: 'var(--accent)', color: 'var(--bg)', border: 'none', borderRadius: 4, cursor: loading ? 'wait' : 'pointer', fontSize: 11, fontWeight: 600 }}
              >
                {loading ? 'Indexing...' : 'Index Repository'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
