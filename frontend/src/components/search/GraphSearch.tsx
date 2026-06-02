import { useState, useMemo, useCallback, useEffect, useRef, type KeyboardEvent } from 'react'
import { searchNodes, getSubgraph } from '../../api/client'
import type { GraphNode, GraphData } from '../../types/api'
import RailSection from '../layout/RailSection'
import LatticeInput from '../ui/LatticeInput'
import LatticeBadge from '../ui/LatticeBadge'
import IconButton from '../ui/IconButton'

interface SearchMatch {
  id: string
  name: string
  label: string
  file_path: string
  ppr_score?: number
  source: 'local' | 'remote'
}

interface GraphSearchProps {
  nodes: GraphNode[]
  onNodeSelect: (node: GraphNode) => void
  onSubgraph?: (graph: GraphData) => void
}

export default function GraphSearch({ nodes, onNodeSelect, onSubgraph }: GraphSearchProps) {
  const [search, setSearch] = useState('')
  const [remoteMatches, setRemoteMatches] = useState<SearchMatch[]>([])
  const [activeIdx, setActiveIdx] = useState(0)
  const [open, setOpen] = useState(false)
  const debounceRef = useRef<number>()
  const listRef = useRef<HTMLDivElement>(null)

  const localMatches = useMemo((): SearchMatch[] => {
    const q = search.trim().toLowerCase()
    if (!q) return []
    return nodes
      .filter(
        n =>
          n.name?.toLowerCase().includes(q) ||
          n.id?.toLowerCase().includes(q) ||
          n.file_path?.toLowerCase().includes(q),
      )
      .slice(0, 12)
      .map(n => ({
        id: n.id,
        name: n.name,
        label: n.label,
        file_path: n.file_path,
        ppr_score: n.ppr_score,
        source: 'local' as const,
      }))
  }, [search, nodes])

  useEffect(() => {
    const q = search.trim()
    if (q.length < 2) {
      setRemoteMatches([])
      return
    }
    if (localMatches.length >= 3) {
      setRemoteMatches([])
      return
    }
    window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => {
      searchNodes(q)
        .then(res =>
          setRemoteMatches(
            res.results
              .filter(r => !localMatches.some(l => l.id === r.qualified_name))
              .slice(0, 20)
              .map(r => ({
                id: r.qualified_name,
                name: r.name,
                label: r.label,
                file_path: r.file_path,
                source: 'remote' as const,
              })),
          ),
        )
        .catch(() => setRemoteMatches([]))
    }, 250)
    return () => window.clearTimeout(debounceRef.current)
  }, [search, localMatches])

  const allMatches = useMemo(() => {
    const merged = [...localMatches]
    for (const r of remoteMatches) {
      if (!merged.some(m => m.id === r.id)) merged.push(r)
    }
    return merged.slice(0, 20)
  }, [localMatches, remoteMatches])

  const showFileSubgraph = search.trim().includes('/') && onSubgraph

  const selectMatch = useCallback(
    (m: SearchMatch) => {
      onNodeSelect({
        id: m.id,
        name: m.name,
        file_path: m.file_path,
        label: (m.label || 'Function') as GraphNode['label'],
        ppr_score: m.ppr_score ?? 0,
        is_seed: false,
        seed_weight: 0,
      })
      setSearch('')
      setOpen(false)
      setActiveIdx(0)
    },
    [onNodeSelect],
  )

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setOpen(false)
      setSearch('')
      return
    }
    if (!open || allMatches.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx(i => Math.min(i + 1, allMatches.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      selectMatch(allMatches[activeIdx])
    }
  }

  useEffect(() => {
    setActiveIdx(0)
  }, [search])

  return (
    <RailSection title="Search" noPadding>
      <div style={{ padding: '0 12px 12px' }}>
        <div style={{ position: 'relative' }}>
          <LatticeInput
            value={search}
            onChange={e => {
              setSearch(e.target.value)
              setOpen(true)
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder="Function, class, or file path…"
            aria-label="Search graph"
          />
          {search && (
            <IconButton
              onClick={() => {
                setSearch('')
                setOpen(false)
              }}
              title="Clear search"
              style={{
                position: 'absolute',
                right: 6,
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: 11,
              }}
            >
              ×
            </IconButton>
          )}
        </div>

        {open && search.trim() && (
          <div
            ref={listRef}
            style={{
              marginTop: 8,
              maxHeight: 180,
              overflowY: 'auto',
              border: '1px solid var(--border)',
              background: 'var(--bg)',
            }}
          >
            {allMatches.map((m, i) => (
              <button
                key={m.id}
                type="button"
                onClick={() => selectMatch(m)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'auto 1fr',
                  gap: 8,
                  width: '100%',
                  textAlign: 'left',
                  padding: '8px 10px',
                  background:
                    i === activeIdx ? 'color-mix(in oklch, var(--accent) 12%, transparent)' : 'transparent',
                  border: 'none',
                  borderBottom: '1px dashed var(--border)',
                  cursor: 'pointer',
                }}
              >
                <LatticeBadge entityLabel={m.label} label="" variant="entity" />
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--text)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {m.name}
                  </div>
                  <div
                    style={{
                      fontSize: 9,
                      color: 'var(--text-muted)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {m.file_path || m.id}
                  </div>
                </div>
              </button>
            ))}

            {showFileSubgraph && (
              <button
                type="button"
                onClick={() => {
                  getSubgraph(search.trim())
                    .then(res => onSubgraph?.(res.graph))
                    .catch(console.error)
                  setOpen(false)
                }}
                style={{
                  width: '100%',
                  padding: '10px',
                  background: 'var(--surface2)',
                  border: 'none',
                  borderTop: '1px solid var(--border)',
                  color: 'var(--accent)',
                  fontSize: 10,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                Focus file subgraph · {search.trim()}
              </button>
            )}

            {allMatches.length === 0 && (
              <div style={{ padding: 10, fontSize: 10, color: 'var(--text-muted)' }}>No matches</div>
            )}
          </div>
        )}

        <div style={{ marginTop: 8, fontSize: 9, color: 'var(--text-muted)' }}>
          ↑↓ navigate · ↵ select · esc clear
        </div>
      </div>
    </RailSection>
  )
}
