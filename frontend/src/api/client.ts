import type {
  QueryRequest,
  QueryResponse,
  TreeResponse,
  NodeDetailResponse,
  SubgraphResponse,
  StatsResponse,
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

export async function getTree(): Promise<TreeResponse> {
  const res = await fetch(`${BASE}/api/tree`)
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

export async function getStats(): Promise<StatsResponse> {
  const res = await fetch(`${BASE}/api/stats`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function openFile(filePath: string, lineNumber?: number): Promise<void> {
  const res = await fetch(`${BASE}/api/open`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: filePath, line_number: lineNumber }),
  })
  if (!res.ok) throw new Error(await res.text())
}
