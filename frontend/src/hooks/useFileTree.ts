import { useState, useEffect, useMemo } from 'react'
import { getTree } from '../api/client'
import type { TreeResponse, TreeNode, PPRFileResult, FileEntry } from '../types/api'

export function useFileTree(pprResults: PPRFileResult[] = []) {
  const [data, setData] = useState<TreeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    getTree()
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false))
  }, [])

  const tree = useMemo(() => {
    if (!data) return []

    const root: TreeNode = {
      name: data.root,
      path: '',
      type: 'directory',
      children: []
    }

    const nodeMap: Record<string, TreeNode> = { '': root }

    // Build the folder structure first
    data.files.forEach((file: FileEntry) => {
      const parts = file.path.split('/')
      let currentPath = ''
      
      parts.forEach((part, i) => {
        const parentPath = currentPath
        currentPath = currentPath ? `${currentPath}/${part}` : part
        
        if (!nodeMap[currentPath]) {
          const newNode: TreeNode = {
            name: part,
            path: currentPath,
            type: i === parts.length - 1 ? file.type : 'directory',
            children: []
          }
          nodeMap[currentPath] = newNode
          nodeMap[parentPath].children?.push(newNode)
        }
      })
    })

    // Sort children: directories first, then files, both alphabetically
    const sortNodes = (node: TreeNode) => {
      if (node.children) {
        node.children.sort((a, b) => {
          if (a.type !== b.type) {
            return a.type === 'directory' ? -1 : 1
          }
          return a.name.localeCompare(b.name)
        })
        node.children.forEach(sortNodes)
      }
    }
    sortNodes(root)

    // Add PPR ranks to file nodes
    pprResults.forEach(res => {
      const node = nodeMap[res.file_path]
      if (node) {
        node.ppr_rank = res.rank
      }
    })

    return root.children || []
  }, [data, pprResults])

  return { tree, loading, error, projectRoot: data?.project_root }
}
