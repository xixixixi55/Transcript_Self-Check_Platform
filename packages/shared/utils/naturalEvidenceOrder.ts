export interface EvidenceOrderCandidate {
  evidence_number: string
}

interface ParsedEvidenceOrder<T> {
  item: T
  position: number
  key: number[]
}

/**
 * Returns the one-time default evidence order without mutating the source
 * array. A natural order is safe only when every evidence number is
 * recognizable and unique; otherwise the parser's original relative order is
 * retained.
 */
export function naturalEvidenceOrder<T extends EvidenceOrderCandidate>(items: readonly T[]): T[] {
  const parsed = items.map((item, position) => ({ item, position, key: parseEvidenceOrder(item.evidence_number) }))
  if (parsed.some(entry => entry.key.length === 0) || hasDuplicateKeys(parsed)) return [...items]

  return parsed
    .sort((left, right) => compareKeys(left.key, right.key) || left.position - right.position)
    .map(entry => entry.item)
}

function parseEvidenceOrder(value: string): number[] {
  if (typeof value !== 'string') return []
  const groups = value.match(/\d+/g)
  if (!groups?.length) return []

  const numbers = groups.map(Number)
  return numbers.every(Number.isSafeInteger) ? numbers : []
}

function hasDuplicateKeys<T>(entries: readonly ParsedEvidenceOrder<T>[]): boolean {
  const keys = new Set<string>()
  return entries.some(entry => {
    const key = entry.key.join(':')
    if (keys.has(key)) return true
    keys.add(key)
    return false
  })
}

function compareKeys(left: readonly number[], right: readonly number[]): number {
  const limit = Math.min(left.length, right.length)
  for (let index = 0; index < limit; index += 1) {
    if (left[index] !== right[index]) return left[index] - right[index]
  }
  return left.length - right.length
}
