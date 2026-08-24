import { describe, expect, it } from 'vitest'
import { generateDiscNumbers, parseDiscSequence } from '@biji/shared/utils'

describe('disc sequence rules', () => {
  it('parses GP date and preserves the entered width', () => {
    const result = parseDiscSequence('gp20260718-09')
    expect(result.valid).toBe(true)
    expect(result.sequence).toMatchObject({
      prefix: 'GP', date: '2026-07-18', start_number: 9, number_width: 2,
    })
  })

  it('rejects invalid dates, whitespace and missing sequence', () => {
    expect(parseDiscSequence('GP20260230-01').error_code).toBe('FIRST_DISC_DATE_INVALID')
    expect(parseDiscSequence('GP20260718 -01').error_code).toBe('FIRST_DISC_NUMBER_INVALID')
    expect(parseDiscSequence('').error_code).toBe('FIRST_DISC_NUMBER_MISSING')
  })

  it('generates one or more numbers and expands after width overflow', () => {
    expect(generateDiscNumbers('GP20260718-09', 1)).toEqual(['GP20260718-09'])
    expect(generateDiscNumbers('GP20260718-09', 3)).toEqual([
      'GP20260718-09', 'GP20260718-10', 'GP20260718-11',
    ])
    expect(generateDiscNumbers('GP20260718-99', 2)).toEqual([
      'GP20260718-99', 'GP20260718-100',
    ])
    expect(generateDiscNumbers('GP20260718-09', 0)).toEqual([])
  })

  it('preserves a configured synthetic Chinese prefix', () => {
    const parsed = parseDiscSequence('测试公20260718-001')
    expect(parsed.valid).toBe(true)
    expect(parsed.sequence?.prefix).toBe('测试公')
    expect(generateDiscNumbers(parsed.sequence!, 2)).toEqual([
      '测试公20260718-001', '测试公20260718-002',
    ])
  })

  it('rejects negative and non-integer counts', () => {
    expect(() => generateDiscNumbers('GP20260718-01', -1)).toThrow('FIRST_DISC_SEQUENCE_INVALID')
    expect(() => generateDiscNumbers('GP20260718-01', 1.5)).toThrow('FIRST_DISC_SEQUENCE_INVALID')
  })
})
