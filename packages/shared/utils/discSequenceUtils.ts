import type { DiscSequence, DiscSequenceParseResult } from '../types/discSequence'

const FIRST_DISC_PATTERN = /^(GP)(\d{4})(\d{2})(\d{2})-(\d+)$/i

function isRealDate(year: number, month: number, day: number): boolean {
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year
    && date.getUTCMonth() === month - 1
    && date.getUTCDate() === day
}

export function parseDiscSequence(value: string): DiscSequenceParseResult {
  if (typeof value !== 'string') return { valid: false, error_code: 'FIRST_DISC_NUMBER_INVALID' }
  if (!value) return { valid: false, error_code: 'FIRST_DISC_NUMBER_MISSING' }
  if (value !== value.trim()) return { valid: false, error_code: 'FIRST_DISC_NUMBER_INVALID' }
  const match = FIRST_DISC_PATTERN.exec(value)
  if (!match) return { valid: false, error_code: 'FIRST_DISC_NUMBER_INVALID' }

  const year = Number(match[2])
  const month = Number(match[3])
  const day = Number(match[4])
  if (!isRealDate(year, month, day)) {
    return { valid: false, error_code: 'FIRST_DISC_DATE_INVALID' }
  }
  const rawNumber = match[5]
  const startNumber = Number(rawNumber)
  if (!Number.isSafeInteger(startNumber) || startNumber < 1) {
    return { valid: false, error_code: 'FIRST_DISC_SEQUENCE_INVALID' }
  }
  return {
    valid: true,
    sequence: {
      prefix: 'GP',
      date: `${match[2]}-${match[3]}-${match[4]}`,
      start_number: startNumber,
      number_width: rawNumber.length,
      first_disc_number: `GP${match[2]}${match[3]}${match[4]}-${rawNumber}`,
    },
  }
}

export function generateDiscNumbers(
  firstDiscNumber: string | DiscSequence,
  count: number,
): string[] {
  if (!Number.isSafeInteger(count) || count < 0) {
    throw new Error('FIRST_DISC_SEQUENCE_INVALID')
  }
  const parsed = typeof firstDiscNumber === 'string'
    ? parseDiscSequence(firstDiscNumber)
    : { valid: true, sequence: firstDiscNumber }
  if (!parsed.valid || !parsed.sequence) {
    throw new Error(parsed.error_code || 'FIRST_DISC_NUMBER_INVALID')
  }
  const sequence = parsed.sequence
  if (count === 0) return []
  if (!Number.isSafeInteger(sequence.start_number + count - 1)) {
    throw new Error('FIRST_DISC_SEQUENCE_INVALID')
  }
  return Array.from({ length: count }, (_, index) => {
    const number = sequence.start_number + index
    return `${sequence.prefix}${sequence.date.replaceAll('-', '')}-${String(number).padStart(sequence.number_width, '0')}`
  })
}

export function formatDiscDate(date: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date)
  return match ? `${match[1]}年${Number(match[2])}月${Number(match[3])}日` : ''
}
