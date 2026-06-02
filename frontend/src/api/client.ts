import type {
  QueryRequest,
  QueryResponse,
  NodeDetailResponse,
  GraphData,
} from '../types/api'

const BASE = ''  // proxied by Vite dev server

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

export interface ProjectHistoryItem {
  name: string
  path: string
  url: string | null
}

export async function getHealth(): Promise<{ 
  status: string; 
  git_info?: { repo: string; commit: string };
  project_history?: ProjectHistoryItem[];
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

export interface GraphStats {
  nodes: Record<string, number>
  edges: Record<string, number>
}

export async function getStats(): Promise<GraphStats> {
  const res = await fetch(`${BASE}/api/stats`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface DependencyRow {
  qualified_name: string
  name: string
  label: string
  file_path: string
  relationship_type: string
}

export async function getDependencies(
  entity: string,
  direction: 'upstream' | 'downstream' | 'both',
  depth: number = 1,
): Promise<{ results: DependencyRow[] }> {
  const params = new URLSearchParams({ entity, direction, depth: String(depth) })
  const res = await fetch(`${BASE}/api/dependencies?${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getDependenciesGraph(
  entity: string,
  direction: 'upstream' | 'downstream' | 'both',
  depth: number = 1,
): Promise<{ graph: import('../types/api').GraphData }> {
  const params = new URLSearchParams({ entity, direction, depth: String(depth) })
  const res = await fetch(`${BASE}/api/dependencies/graph?${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
