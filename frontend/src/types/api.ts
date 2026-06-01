// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface QueryRequest {
  task: string
  top_k?: number
}

// ---------------------------------------------------------------------------
// Response building blocks — mirror Pydantic models in server.py
// ---------------------------------------------------------------------------

export interface SeedInfo {
  id: string
  name: string
  /** "entity" for high-weight seeds, "bm25" for BM25-derived seeds */
  signal: 'entity' | 'bm25'
  weight: number
}

export interface PPREntityResult {
  rank: number
  qualified_name: string
  name: string
  label: string
  file_path: string
  score: number
  /** Human-readable path from the file to a seed node */
  path: string
  line_number: number
  line_end: number
}

export interface BM25FileResult {
  rank: number
  file_path: string
}

// ---------------------------------------------------------------------------
// Graph node — annotated dict produced in server.py _run_query
// ---------------------------------------------------------------------------

export interface GraphNode {
  /** qualified_name: "<file_path>::<name>" */
  id: string
  label: 'File' | 'Class' | 'Function' | 'Method'
  name: string
  file_path: string
  ppr_score: number
  is_seed: boolean
  seed_weight: number
  line_number?: number
  line_end?: number
}

export interface GraphEdge {
  source: string
  target: string
  type: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// ---------------------------------------------------------------------------
// Top-level query response
// ---------------------------------------------------------------------------

export interface QueryResponse {
  seeds: SeedInfo[]
  ppr_results: PPREntityResult[]
  bm25_results: BM25FileResult[]
  graph: GraphData
  damping_factor: number
  top_k: number
  git_info?: { repo: string; commit: string }
}

// ---------------------------------------------------------------------------
// Node detail  (/api/node/:qualified_name)
// ---------------------------------------------------------------------------

export interface NodeRelation {
  qualified_name: string
  name: string
  label: string
  file_path: string
  relationship: string
}

export interface NodeDetailResponse {
  node: GraphNode
  incoming: NodeRelation[]
  outgoing: NodeRelation[]
  source_snippet?: string
}

// ---------------------------------------------------------------------------
// Subgraph  (/api/subgraph?focus=<file_path>)
// ---------------------------------------------------------------------------

export interface SubgraphResponse {
  graph: GraphData
  focus_path: string
}
