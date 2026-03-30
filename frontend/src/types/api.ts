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
  name: string
  /** "entity" for high-weight seeds, "bm25" for BM25-derived seeds */
  signal: 'entity' | 'bm25'
  weight: number
}

export interface PPRFileResult {
  rank: number
  file_path: string
  score: number
  /** Human-readable path from the file to a seed node */
  path: string
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
  ppr_results: PPRFileResult[]
  bm25_results: BM25FileResult[]
  graph: GraphData
}

// ---------------------------------------------------------------------------
// File tree types  (/api/tree)
// ---------------------------------------------------------------------------

export interface TreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: TreeNode[]
  entity_count?: number
}

export interface TreeResponse {
  tree: TreeNode[]
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

// ---------------------------------------------------------------------------
// Stats  (/api/stats)
// ---------------------------------------------------------------------------

export interface StatsResponse {
  node_count: number
  edge_count: number
  file_count: number
  label_counts: Record<string, number>
  edge_type_counts: Record<string, number>
}
