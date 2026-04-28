/** Returns the CSS color for a node label type (reads CSS variables at runtime). */
export function nodeColor(label: string): string {
  const style = getComputedStyle(document.documentElement)
  switch (label) {
    case 'File':     return style.getPropertyValue('--node-file').trim() || 'oklch(0.70 0.12 240)'
    case 'Class':    return style.getPropertyValue('--node-class').trim() || 'oklch(0.74 0.14 145)'
    case 'Function': return style.getPropertyValue('--node-function').trim() || 'oklch(0.80 0.14 75)'
    case 'Method':   return style.getPropertyValue('--node-method').trim() || 'oklch(0.74 0.14 290)'
    default:         return style.getPropertyValue('--text-muted').trim() || 'oklch(0.55 0.010 70)'
  }
}

/** Returns the CSS color for an edge relationship type. */
export function edgeColor(type: string): string {
  const style = getComputedStyle(document.documentElement)
  switch (type) {
    case 'CALLS':         return style.getPropertyValue('--edge-calls').trim() || 'oklch(0.68 0.13 145)'
    case 'IMPORTS':       return style.getPropertyValue('--edge-imports').trim() || 'oklch(0.68 0.12 240)'
    case 'CONTAINS':      return style.getPropertyValue('--edge-contains').trim() || 'oklch(0.45 0.008 60)'
    case 'INHERITS_FROM': return style.getPropertyValue('--edge-inherits').trim() || 'oklch(0.72 0.14 35)'
    default:              return style.getPropertyValue('--text-muted').trim() || 'oklch(0.55 0.010 70)'
  }
}

export function formatScore(score: number): string {
  return score.toFixed(4)
}
