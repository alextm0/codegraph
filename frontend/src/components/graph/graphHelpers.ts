/** Returns the hex color for a node label type. */
export function nodeColor(label: string): string {
  switch (label) {
    case 'File':     return '#60a5fa'
    case 'Class':    return '#4ade80'
    case 'Function': return '#fbbf24'
    case 'Method':   return '#a78bfa'
    default:         return '#475569'
  }
}

/** Returns the hex color for an edge relationship type. */
export function edgeColor(type: string): string {
  switch (type) {
    case 'CALLS':        return '#22c55e'
    case 'IMPORTS':      return '#3b82f6'
    case 'CONTAINS':     return '#475569'
    case 'INHERITS_FROM': return '#f97316'
    default:             return '#475569'
  }
}

/** Formats a PPR score to 4 decimal places. */
export function formatScore(score: number): string {
  return score.toFixed(4)
}
