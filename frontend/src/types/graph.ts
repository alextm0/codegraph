import type { GraphNode } from './api'
import type { SimulationNodeDatum, SimulationLinkDatum } from 'd3'

export type D3Node = SimulationNodeDatum & GraphNode

export interface D3Edge extends SimulationLinkDatum<D3Node> {
  source: string | D3Node
  target: string | D3Node
  type: string
}
