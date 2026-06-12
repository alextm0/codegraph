import type {
  QueryRequest,
  QueryResponse,
  NodeDetailResponse,
  GraphData,
} from '../types/api'

const BASE = ''

export async function postQuery(req: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getNodeDetail(qualifiedName: string): Promise<NodeDetailResponse> {
  const res = await fetch(`${BASE}/api/node/${encodeURIComponent(qualifiedName)}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function openInIDE(filePath: string, line: number): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/api/open?file_path=${encodeURIComponent(filePath)}&line=${line}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function initializeProject(target: string): Promise<{ status: string; path: string }> {
  const res = await fetch(`${BASE}/api/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function rebuildProject(): Promise<{ status: string; path: string }> {
  const res = await fetch(`${BASE}/api/rebuild`, { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface ProjectHistoryItem {
  name: string
  path: string
  url: string | null
}

export async function getHealth(): Promise<{
  status: string
  git_info?: { repo: string; commit: string }
  project_history?: ProjectHistoryItem[]
}> {
  const res = await fetch(`${BASE}/api/health`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getBaseGraph(): Promise<GraphData> {
  const res = await fetch(`${BASE}/api/graph/base`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface ConnectedFileRow {
  entity_count: number
  file_path: string
}

export interface GraphStats {
  nodes: Record<string, number>
  edges: Record<string, number>
  most_connected_files?: ConnectedFileRow[]
  last_build?: string | null
}

export async function getStats(): Promise<GraphStats> {
  const res = await fetch(`${BASE}/api/stats`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface FileSourceResponse {
  file_path: string
  content: string
  line_count: number
  entities: { qualified_name: string; name: string; label: string }[]
}

export async function getFile(filePath: string): Promise<FileSourceResponse> {
  const params = new URLSearchParams({ file_path: filePath })
  const res = await fetch(`${BASE}/api/files/source?${params}`)
  if (!res.ok) {
    const body = await res.text()
    try {
      const parsed = JSON.parse(body) as { detail?: string }
      throw new Error(parsed.detail ?? body)
    } catch (e) {
      if (e instanceof Error && e.message !== body) throw e
      throw new Error(body || `HTTP ${res.status}`)
    }
  }
  return res.json()
}
