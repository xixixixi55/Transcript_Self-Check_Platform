import { describe, expect, it } from 'vitest'
import { allPartsDiscMapped, resolveArchiveCompletionStatus } from '@biji/shared/utils'

describe('resolveArchiveCompletionStatus', () => {
  it('maps exported lifecycle to exported', () => {
    expect(resolveArchiveCompletionStatus('exported', false)).toBe('exported')
  })

  it('maps archive_verified without disc mapping to disc_pending', () => {
    expect(resolveArchiveCompletionStatus('archive_verified', false)).toBe('disc_pending')
  })

  it('maps archive_verified with disc mapping to archive_complete', () => {
    expect(resolveArchiveCompletionStatus('archive_verified', true)).toBe('archive_complete')
  })

  it('maps active compression to compressing', () => {
    expect(resolveArchiveCompletionStatus('archiving', false)).toBe('compressing')
    expect(resolveArchiveCompletionStatus('archive_queued', false)).toBe('compressing')
  })

  it('returns null for non-archive states', () => {
    expect(resolveArchiveCompletionStatus('review_ready', false)).toBeNull()
  })
})

describe('allPartsDiscMapped', () => {
  it('is false for empty or missing parts', () => {
    expect(allPartsDiscMapped([])).toBe(false)
    expect(allPartsDiscMapped(null)).toBe(false)
    expect(allPartsDiscMapped(undefined)).toBe(false)
  })

  it('requires every part to carry a disc number', () => {
    expect(allPartsDiscMapped([{ disc_number: 'GP20260718-01' }])).toBe(true)
    expect(allPartsDiscMapped([{ disc_number: 'GP20260718-01' }, { disc_number: '' }])).toBe(false)
    expect(allPartsDiscMapped([{ disc_number: 'GP20260718-01' }, { disc_number: null }])).toBe(false)
  })
})
