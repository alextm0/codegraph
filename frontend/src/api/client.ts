import type {
  QueryRequest,
  QueryResponse,
  NodeDetailResponse,
  GraphData,
  SubgraphResponse,
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

export interface SearchResultRow {
  qualified_name: string
  name: string
  label: string
  file_path: string
}

export async function searchNodes(q: string): Promise<{ results: SearchResultRow[] }> {
  const params = new URLSearchParams({ q })
  const res = await fetch(`${BASE}/api/search?${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getSubgraph(focus: string): Promise<SubgraphResponse> {
  const params = new URLSearchParams({ focus })
  const res = await fetch(`${BASE}/api/subgraph?${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface DoctorCheck {
  name: string
  ok: boolean
  message: string
  fix_hint: string | null
  severity: string
}

export async function getDoctor(): Promise<{ ok: boolean; checks: DoctorCheck[] }> {
  const res = await fetch(`${BASE}/api/doctor`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface DeadCodeRow {
  qualified_name: string
  name: string
  label: string
  file_path: string
}

export async function getDeadCode(limit = 50): Promise<{ results: DeadCodeRow[]; total: number }> {
  const params = new URLSearchParams({ limit: String(limit) })
  const res = await fetch(`${BASE}/api/dead-code?${params}`)
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

export async function getDependenciesGraph(
  entity: string,
  direction: 'upstream' | 'downstream' | 'both',
  depth: number = 1,
): Promise<{ graph: GraphData }> {
  const params = new URLSearchParams({ entity, direction, depth: String(depth) })
  const res = await fetch(`${BASE}/api/dependencies/graph?${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
