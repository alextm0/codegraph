import type {
  QueryRequest,
  QueryResponse,
  NodeDetailResponse,
  SubgraphResponse,
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

export async function getSubgraph(focusPath: string): Promise<SubgraphResponse> {
  const res = await fetch(`${BASE}/api/subgraph?focus=${encodeURIComponent(focusPath)}`)
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

export async function getHealth(): Promise<{ status: string; git_info?: { repo: string; commit: string } }> {
  const res = await fetch(`${BASE}/api/health`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getBaseGraph(): Promise<GraphData> {
  const res = await fetch(`${BASE}/api/graph/base`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
