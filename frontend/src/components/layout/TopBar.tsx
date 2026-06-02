import { useState } from 'react'
import { useTheme } from '../../context/ThemeContext'
import ProjectSettingsModal from './ProjectSettingsModal'

import { ProjectHistoryItem } from '../../api/client'

interface TopBarProps {
  gitInfo?: { repo: string; commit: string }
  projectHistory?: ProjectHistoryItem[]
  onGraphRefresh?: () => void
}

export default function TopBar({
  gitInfo, projectHistory = [], onGraphRefresh,
}: TopBarProps) {
  const { theme, toggleTheme } = useTheme()
  const [showProjectModal, setShowProjectModal] = useState(false)

  return (
    <>
      {showProjectModal && (
        <ProjectSettingsModal 
          onClose={() => setShowProjectModal(false)} 
          history={projectHistory}
          onIndexed={onGraphRefresh}
        />
      )}
      
      {/* Primary top bar — 40px */}
      <div
        style={{
          gridColumn: '1 / -1',
          height: 'var(--topbar-h)',
          display: 'flex',
          alignItems: 'center',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
          flexShrink: 0,
        }}
      >
        {/* Wordmark */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '0 16px',
            height: '100%',
            borderRight: '1px solid var(--border)',
          }}
        >
          <LatticeLogoMark />
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: '0.06em',
              color: 'var(--text)',
            }}
          >
            CODEGRAPH
          </span>
        </div>

        {gitInfo && (
          <div style={{ display: 'flex', height: '100%', alignItems: 'center' }}>
            <MetaChip label="repo" value={gitInfo.repo} />
            <MetaChip label="commit" value={gitInfo.commit} />
            <button
              onClick={() => setShowProjectModal(true)}
              style={{
                height: '100%',
                padding: '0 12px',
                background: 'none',
                border: 'none',
                borderLeft: '1px solid var(--border)',
                color: 'var(--text-muted)',
                fontSize: 9,
                letterSpacing: '0.10em',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                transition: 'color 120ms',
              }}
              onMouseEnter={e => e.currentTarget.style.color = 'var(--accent)'}
              onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
            >
              [SWITCH]
            </button>
          </div>
        )}

        <div style={{ flex: 1 }} />

        <button
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          style={{
            height: '100%',
            padding: '0 12px',
            background: 'none',
            border: 'none',
            borderLeft: '1px solid var(--border)',
            color: 'var(--text-muted)',
            fontSize: 10,
            letterSpacing: '0.10em',
            cursor: 'pointer',
            transition: 'color 120ms, background 120ms',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.color = 'var(--text)'
            e.currentTarget.style.background = 'var(--surface2)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = 'var(--text-muted)'
            e.currentTarget.style.background = 'none'
          }}
        >
          {theme === 'dark' ? '[LIGHT]' : '[DARK]'}
        </button>
      </div>
    </>
  )
}

function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: '0 14px',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        borderLeft: '1px solid var(--border)',
        fontSize: 10,
        fontVariantNumeric: 'tabular-nums slashed-zero',
      }}
    >
      <span
        style={{
          color: 'var(--text-muted)',
          letterSpacing: '0.10em',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </span>
      <span style={{ color: 'var(--text)' }}>{value}</span>
    </div>
  )
}

function LatticeLogoMark() {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" style={{ flexShrink: 0 }}>
      <rect x={2} y={2} width={6} height={6} fill="var(--accent)" />
      <rect x={12} y={2} width={6} height={6} fill="none" stroke="var(--accent)" strokeWidth={1} />
      <rect x={2} y={12} width={6} height={6} fill="none" stroke="var(--accent)" strokeWidth={1} />
      <rect x={12} y={12} width={6} height={6} fill="var(--accent)" />
      <line x1={8} y1={5} x2={12} y2={5} stroke="var(--accent)" strokeWidth={1} />
      <line x1={5} y1={8} x2={5} y2={12} stroke="var(--accent)" strokeWidth={1} />
      <line x1={15} y1={8} x2={15} y2={12} stroke="var(--accent)" strokeWidth={1} />
      <line x1={8} y1={15} x2={12} y2={15} stroke="var(--accent)" strokeWidth={1} />
    </svg>
  )
}
