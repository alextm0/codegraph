import type { GraphNode } from '../types/api'

export interface FileTreeNode {
  id: string
  name: string
  path: string
  kind: 'folder' | 'file'
  children: FileTreeNode[]
  entityCount: number
}

/** Build a folder/file tree from graph nodes' file_path values. */
export function buildFileTree(nodes: GraphNode[]): FileTreeNode {
  const root: FileTreeNode = {
    id: '',
    name: '',
    path: '',
    kind: 'folder',
    children: [],
    entityCount: 0,
  }

  const filePaths = new Set<string>()
  for (const n of nodes) {
    if (n.file_path) filePaths.add(n.file_path)
  }

  const sorted = [...filePaths].sort()

  for (const filePath of sorted) {
    const parts = filePath.split('/')
    let current = root
    let built = ''

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const isFile = i === parts.length - 1
      built = built ? `${built}/${part}` : part

      let child = current.children.find(c => c.name === part && c.kind === (isFile ? 'file' : 'folder'))
      if (!child) {
        child = {
          id: built,
          name: part,
          path: built,
          kind: isFile ? 'file' : 'folder',
          children: [],
          entityCount: 0,
        }
        current.children.push(child)
      }
      current = child
    }

    const count = nodes.filter(n => n.file_path === filePath).length
    const fileNode = findNode(root, filePath)
    if (fileNode) fileNode.entityCount = count
  }

  sortTree(root)
  return root
}

function findNode(node: FileTreeNode, path: string): FileTreeNode | null {
  if (node.path === path) return node
  for (const c of node.children) {
    const found = findNode(c, path)
    if (found) return found
  }
  return null
}

function sortTree(node: FileTreeNode): void {
  node.children.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1
    return a.name.localeCompare(b.name)
  })
  node.children.forEach(sortTree)
}

/** Collect folder paths that should be expanded to reveal matches. */
export function expandPathsForFilter(tree: FileTreeNode, query: string): Set<string> {
  const expanded = new Set<string>()
  const q = query.trim().toLowerCase()
  if (!q) return expanded

  const walk = (node: FileTreeNode, ancestors: string[]): boolean => {
    const selfMatch =
      node.kind === 'file' && node.path.toLowerCase().includes(q) ||
      node.name.toLowerCase().includes(q)

    let childMatch = false
    for (const c of node.children) {
      if (walk(c, [...ancestors, node.path])) childMatch = true
    }

    if (selfMatch || childMatch) {
      ancestors.forEach(p => { if (p) expanded.add(p) })
      if (node.kind === 'folder') expanded.add(node.path)
      return true
    }
    return false
  }

  walk(tree, [])
  return expanded
}

/** Filter tree nodes by query (keeps ancestors of matches). */
export function filterFileTree(node: FileTreeNode, query: string): FileTreeNode | null {
  const q = query.trim().toLowerCase()
  if (!q) return node

  const filter = (n: FileTreeNode): FileTreeNode | null => {
    const nameMatch = n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q)
    const filteredChildren = n.children
      .map(filter)
      .filter((c): c is FileTreeNode => c !== null)

    if (nameMatch || filteredChildren.length > 0) {
      return { ...n, children: filteredChildren }
    }
    return null
  }

  return filter(node)
}
