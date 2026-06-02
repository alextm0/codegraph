import { useMemo, useState } from 'react'
import type { GraphNode } from '../../types/api'
import {
  buildFileTree,
  expandPathsForFilter,
  filterFileTree,
  type FileTreeNode,
} from '../../utils/buildFileTree'
import LatticeInput from '../ui/LatticeInput'

interface ProjectTreeProps {
  nodes: GraphNode[]
  selectedFilePath: string | null
  onFileSelect: (filePath: string) => void
}

/* ── File-type metadata (icon tint by extension) ─────────────── */
function fileExt(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}

function extColor(ext: string): string {
  switch (ext) {
    case 'py':            return 'var(--node-file)'
    case 'ts':
    case 'tsx':           return 'var(--edge-imports)'
    case 'js':
    case 'jsx':           return 'var(--node-function)'
    case 'json':
    case 'yaml':
    case 'yml':
    case 'toml':          return 'var(--node-method)'
    case 'md':
    case 'txt':           return 'var(--text-muted)'
    case 'css':           return 'var(--node-class)'
    default:              return 'var(--text-dim)'
  }
}

function FileGlyph({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
      <path
        d="M4 1.5h5L13 5v8.5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1Z"
        fill={color}
        fillOpacity="0.16"
        stroke={color}
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
      <path d="M9 1.5V5h4" stroke={color} strokeWidth="1.1" strokeLinejoin="round" />
    </svg>
  )
}

function FolderGlyph({ open }: { open: boolean }) {
  const color = 'var(--text-dim)'
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
      <path
        d={
          open
            ? 'M2 4.5a1 1 0 0 1 1-1h3l1.2 1.4H13a1 1 0 0 1 1 1V7H4.2L2 12.5V4.5Z'
            : 'M2 4a1 1 0 0 1 1-1h3l1.2 1.4H13a1 1 0 0 1 1 1v6.1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4Z'
        }
        fill={color}
        fillOpacity="0.18"
        stroke={color}
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
      {open && (
        <path
          d="M2 12.5 4.2 7H15l-2.1 5a1 1 0 0 1-.95.7H3a1 1 0 0 1-1-1.2Z"
          fill={color}
          fillOpacity="0.1"
          stroke={color}
          strokeWidth="1.1"
          strokeLinejoin="round"
        />
      )}
    </svg>
  )
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 10 10"
      fill="none"
      style={{
        flexShrink: 0,
        transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
        transition: 'transform var(--dur-fast)',
      }}
    >
      <path d="M3.5 2.5 6.5 5 3.5 7.5" stroke="var(--text-muted)" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function ProjectTree({ nodes, selectedFilePath, onFileSelect }: ProjectTreeProps) {
  const [filter, setFilter] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())

  const root = useMemo(() => buildFileTree(nodes), [nodes])
  const fileCount = useMemo(() => countFiles(root), [root])
  const allFolderPaths = useMemo(() => collectFolderPaths(root), [root])

  const filteredRoot = useMemo(
    () => (filter.trim() ? filterFileTree(root, filter) : root),
    [root, filter],
  )

  const autoExpanded = useMemo(
    () => (filter.trim() ? expandPathsForFilter(root, filter) : new Set<string>()),
    [root, filter],
  )

  const toggleFolder = (path: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const expandAll = () => setExpanded(new Set(allFolderPaths))
  const collapseAll = () => setExpanded(new Set())

  const isExpanded = (path: string) =>
    filter.trim() ? autoExpanded.has(path) : expanded.has(path) || path === ''

  if (!filteredRoot || filteredRoot.children.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
        <div style={{ padding: '12px 14px', flexShrink: 0 }}>
          <LatticeInput
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Search files…"
            aria-label="Search project files"
          />
        </div>
        <div style={{ padding: 20, fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55 }}>
          {filter.trim() ? 'No files match your search.' : 'No indexed files yet.'}
          {!filter.trim() && (
            <div style={{ marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 11 }}>codegraph rebuild</div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ padding: '12px 14px 10px', flexShrink: 0 }}>
        <LatticeInput
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Search files…"
          aria-label="Search project files"
        />
        <div
          style={{
            marginTop: 9,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 11,
            color: 'var(--text-muted)',
          }}
        >
          <span>
            {fileCount} files · <span className="font-mono">{nodes.length.toLocaleString()}</span> entities
          </span>
          <span style={{ display: 'flex', gap: 4 }}>
            <ToolbarBtn title="Expand all folders" onClick={expandAll} disabled={!!filter.trim()}>
              ⊞
            </ToolbarBtn>
            <ToolbarBtn title="Collapse all folders" onClick={collapseAll} disabled={!!filter.trim()}>
              ⊟
            </ToolbarBtn>
          </span>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '0 6px 12px' }}>
        {filteredRoot.children.map(child => (
          <TreeRow
            key={child.id}
            node={child}
            depth={0}
            selectedFilePath={selectedFilePath}
            isExpanded={isExpanded}
            onToggleFolder={toggleFolder}
            onFileSelect={onFileSelect}
          />
        ))}
      </div>
    </div>
  )
}

function ToolbarBtn({
  children,
  title,
  onClick,
  disabled,
}: {
  children: React.ReactNode
  title: string
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      className="focus-ring"
      style={{
        width: 22,
        height: 22,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        background: 'transparent',
        color: 'var(--text-muted)',
        fontSize: 12,
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        transition: 'background var(--dur-fast), color var(--dur-fast)',
      }}
      onMouseEnter={e => {
        if (!disabled) {
          e.currentTarget.style.background = 'var(--surface2)'
          e.currentTarget.style.color = 'var(--text)'
        }
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'var(--text-muted)'
      }}
    >
      {children}
    </button>
  )
}

function countFiles(node: FileTreeNode): number {
  let n = node.kind === 'file' ? 1 : 0
  for (const c of node.children) n += countFiles(c)
  return n
}

function collectFolderPaths(node: FileTreeNode, acc: string[] = []): string[] {
  if (node.kind === 'folder' && node.path) acc.push(node.path)
  for (const c of node.children) collectFolderPaths(c, acc)
  return acc
}

function TreeRow({
  node,
  depth,
  selectedFilePath,
  isExpanded,
  onToggleFolder,
  onFileSelect,
}: {
  node: FileTreeNode
  depth: number
  selectedFilePath: string | null
  isExpanded: (path: string) => boolean
  onToggleFolder: (path: string) => void
  onFileSelect: (path: string) => void
}) {
  const indent = 8 + depth * 13
  const open = node.kind === 'folder' && isExpanded(node.path)

  if (node.kind === 'file') {
    const active = selectedFilePath === node.path
    const color = extColor(fileExt(node.name))
    return (
      <button
        type="button"
        onClick={() => onFileSelect(node.path)}
        title={node.path}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          width: '100%',
          padding: `6px 8px 6px ${indent + 14}px`,
          marginBottom: 1,
          border: 'none',
          borderLeft: active ? '2px solid var(--accent)' : '2px solid transparent',
          borderRadius: 'var(--radius-sm)',
          background: active
            ? 'color-mix(in oklch, var(--accent) 14%, transparent)'
            : 'transparent',
          cursor: 'pointer',
          textAlign: 'left',
          fontFamily: 'var(--font-body)',
          transition: 'background var(--dur-fast)',
        }}
        onMouseEnter={e => {
          if (!active) e.currentTarget.style.background = 'var(--surface2)'
        }}
        onMouseLeave={e => {
          if (!active) e.currentTarget.style.background = 'transparent'
        }}
      >
        <FileGlyph color={active ? 'var(--accent)' : color} />
        <span
          style={{
            fontSize: 12.5,
            color: active ? 'var(--accent)' : 'var(--text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}
        >
          {node.name}
        </span>
        {node.entityCount > 0 && (
          <span
            className="font-mono"
            style={{
              fontSize: 10,
              color: 'var(--text-muted)',
              flexShrink: 0,
              background: 'var(--surface2)',
              borderRadius: 'var(--radius-sm)',
              padding: '1px 5px',
            }}
          >
            {node.entityCount}
          </span>
        )}
      </button>
    )
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => onToggleFolder(node.path)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          width: '100%',
          padding: `6px 8px 6px ${indent}px`,
          marginBottom: 1,
          border: 'none',
          borderRadius: 'var(--radius-sm)',
          background: 'transparent',
          cursor: 'pointer',
          textAlign: 'left',
          fontFamily: 'var(--font-body)',
          fontSize: 12.5,
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface2)' }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
      >
        <Chevron open={open} />
        <FolderGlyph open={open} />
        <span style={{ fontWeight: 500, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.name}
        </span>
      </button>
      {open &&
        node.children.map(child => (
          <TreeRow
            key={child.id}
            node={child}
            depth={depth + 1}
            selectedFilePath={selectedFilePath}
            isExpanded={isExpanded}
            onToggleFolder={onToggleFolder}
            onFileSelect={onFileSelect}
          />
        ))}
    </div>
  )
}
