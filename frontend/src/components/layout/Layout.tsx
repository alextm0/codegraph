import type { QueryResponse, GraphNode } from '../../types/api'

interface LayoutProps {
  queryResult: QueryResponse | null
  selectedNode: GraphNode | null
  focusPath: string | null
  onQueryResult: (result: QueryResponse) => void
  onNodeSelect: (node: GraphNode | null) => void
  onFocusPath: (path: string | null) => void
}

export default function Layout(_props: LayoutProps) {
  return (
    <div>
      <p>CodeGraph Visualizer (loading...)</p>
    </div>
  )
}
