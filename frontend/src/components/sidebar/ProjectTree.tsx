import React, { useState } from 'react'
import { TreeNode as TreeNodeType } from '../../types/api'
import { openFile } from '../../api/client'

interface ProjectTreeProps {
  tree: TreeNodeType[]
  onFocusPath: (path: string | null) => void
  currentFocus: string | null
  loading?: boolean
}

export default function ProjectTree({ tree, onFocusPath, currentFocus, loading = false }: ProjectTreeProps) {
  return (
    <div className="project-tree" style={{ flex: 1, overflow: 'auto', minHeight: 0, paddingTop: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontWeight: 'bold', fontSize: '0.9rem', color: 'var(--text-muted)', flex: 1 }}>
          PROJECT EXPLORER
        </div>
        {currentFocus && (
          <button
            onClick={() => onFocusPath(null)}
            title="Clear focus"
            style={{
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '0.7rem',
              padding: '1px 6px',
            }}
          >
            ✕ clear
          </button>
        )}
      </div>
      {currentFocus && (
        <div style={{
          fontSize: '0.75rem',
          color: 'var(--accent2)',
          marginBottom: 8,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          fontFamily: 'var(--mono)',
        }}>
          Focused: {currentFocus}
        </div>
      )}
      {loading && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', padding: '8px 4px' }}>
          Loading…
        </div>
      )}
      {!loading && tree.map(node => (
        <TreeNode
          key={node.path}
          node={node}
          depth={0}
          onFocusPath={onFocusPath}
          currentFocus={currentFocus}
        />
      ))}
    </div>
  )
}

interface TreeNodeProps {
  node: TreeNodeType
  depth: number
  onFocusPath: (path: string | null) => void
  currentFocus: string | null
}

function TreeNode({ node, depth, onFocusPath, currentFocus }: TreeNodeProps) {
  const [isOpen, setIsOpen] = useState(false)
  const isSelected = currentFocus === node.path

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (node.type === 'directory') {
      setIsOpen(!isOpen)
    }
  }

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onFocusPath(isSelected ? null : node.path)
  }

  const handleOpen = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (node.type === 'file') {
      openFile(node.path).catch(console.error)
    }
  }

  return (
    <div className="tree-node-container">
      <div
        className={`tree-node ${isSelected ? 'selected' : ''}`}
        style={{
          paddingLeft: depth * 12 + 4,
          paddingRight: 4,
          paddingTop: 2,
          paddingBottom: 2,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: '0.85rem',
          backgroundColor: isSelected ? 'var(--bg-accent)' : 'transparent',
          borderRadius: 4,
          color: node.ppr_rank ? 'var(--ppr-color)' : 'inherit'
        }}
        onClick={handleClick}
      >
        <span
          onClick={handleToggle}
          style={{
            display: 'inline-block',
            width: 12,
            textAlign: 'center',
            opacity: node.type === 'directory' ? 0.7 : 0,
            transform: isOpen ? 'rotate(90deg)' : 'none',
            transition: 'transform 0.1s'
          }}
        >
          {node.type === 'directory' ? '▶' : ''}
        </span>
        <span style={{ opacity: 0.7 }}>
          {node.type === 'directory' ? '📁' : '📄'}
        </span>
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={node.name}>
          {node.name}
        </span>
        {node.type === 'file' && (
          <button
            onClick={handleOpen}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text)',
              opacity: 0.4,
              fontSize: '1rem',
              padding: '0 4px',
              fontFamily: 'var(--mono)',
            }}
            title="Open in Editor"
            onMouseEnter={e => e.currentTarget.style.opacity = '1'}
            onMouseLeave={e => e.currentTarget.style.opacity = '0.4'}
          >
            ↗
          </button>
        )}
        {node.ppr_rank && (
          <span
            style={{
              fontSize: '0.7rem',
              backgroundColor: 'var(--ppr-color)',
              color: 'black',
              padding: '0 4px',
              borderRadius: 8,
              minWidth: 16,
              textAlign: 'center'
            }}
          >
            {node.ppr_rank}
          </span>
        )}
      </div>
      {isOpen && node.children && (
        <div className="tree-node-children">
          {node.children.map(child => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              onFocusPath={onFocusPath}
              currentFocus={currentFocus}
            />
          ))}
        </div>
      )}
    </div>
  )
}
