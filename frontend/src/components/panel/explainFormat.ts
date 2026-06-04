import type { PPREntityResult } from '../../types/api'

/** Short display name from a qualified_name or path segment. */
export function shortName(idOrName: string): string {
  if (!idOrName) return '?'
  const afterScope = idOrName.includes('::') ? idOrName.split('::').pop()! : idOrName
  const base = afterScope.split('/').pop() ?? afterScope
  return base.length > 40 ? `${base.slice(0, 37)}…` : base
}

/** One calm line of provenance for a ranked entity. */
export function oneLineWhy(result: PPREntityResult): string {
  if (result.path === 'direct seed') return 'Matched task — seed'

  const ids = result.path_ids ?? []
  if (ids.length >= 2) {
    const chain = ids.map(shortName).join(' → ')
    if (chain.length <= 72) return chain
    return `${ids.length - 1} hops from seed`
  }

  switch (result.contribution) {
    case 'lexical':
      return 'From a text-matched seed'
    case 'both':
      return 'On a path from a seed'
    default:
      return 'Nearby in the graph'
  }
}

export function seedKind(signal: string): string {
  return signal === 'entity' ? 'entity' : 'bm25'
}
