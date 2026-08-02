import { describe, expect, it } from 'vitest'
import { expiresAtUtc, isTrustedUtcTimestamp, isUtcIsoTimestamp } from '@biji/shared/utils'

describe('retention contract rules', () => {
  it('accepts only UTC-aware timestamps for durable retention facts', () => {
    expect(isUtcIsoTimestamp('2026-08-02T05:30:00Z')).toBe(true)
    expect(isUtcIsoTimestamp('2026-08-02T13:30:00+08:00')).toBe(false)
    expect(isUtcIsoTimestamp('2026-08-02T05:30:00')).toBe(false)
  })

  it('uses the five-minute trusted-clock boundary', () => {
    const now = Date.parse('2026-08-02T05:30:00Z')
    expect(isTrustedUtcTimestamp('2026-08-02T05:35:00Z', now)).toBe(true)
    expect(isTrustedUtcTimestamp('2026-08-02T05:35:01Z', now)).toBe(false)
  })

  it('adds continuous 24-hour days without changing the UTC instant', () => {
    expect(expiresAtUtc('2026-08-02T05:30:00Z', 30)).toBe('2026-09-01T05:30:00.000Z')
    expect(() => expiresAtUtc(
      '2026-08-02T05:35:01Z', 30, Date.parse('2026-08-02T05:30:00Z'),
    )).toThrow('RETENTION_TIME_IN_FUTURE')
  })
})
