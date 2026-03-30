import type { SimulationNodeDatum, SimulationLinkDatum } from 'd3'

export interface D3Node extends SimulationNodeDatum {
  id: string
  label: 'File' | 'Class' | 'Function' | 'Method'
  name: string
  file_path: string
  ppr_score: number
  is_seed: boolean
  seed_weight: number
}

export interface D3Edge extends SimulationLinkDatum<D3Node> {
  source: string | D3Node
  target: string | D3Node
  type: string
}
