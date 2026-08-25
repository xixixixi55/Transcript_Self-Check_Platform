import { describe, expect, it } from 'vitest'
import {
  allPartsDiscMapped,
  archivePartsTotalBytes,
  resolveArchiveCompletionStatus,
  unifiedExportRequestTimeoutMs,
} from '@biji/shared/utils'
import {
  UNIFIED_EXPORT_MAX_REQUEST_TIMEOUT_MS,
  UNIFIED_EXPORT_REQUEST_TIMEOUT_MS,
} from '@biji/shared/constants'

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

describe('HDD-oriented unified export timeout', () => {
  it('requires complete positive part-size evidence', () => {
    expect(archivePartsTotalBytes(null)).toBeNull()
    expect(archivePartsTotalBytes([])).toBeNull()
    expect(archivePartsTotalBytes([{ size_bytes: 10 }, { size_bytes: 20 }])).toBe(30)
    expect(archivePartsTotalBytes([{ size_bytes: 10 }, { size_bytes: 0 }])).toBeNull()
    expect(archivePartsTotalBytes([{ size_bytes: Number.NaN }])).toBeNull()
    expect(archivePartsTotalBytes([{ size_bytes: 1.5 }, { size_bytes: 2.5 }])).toBeNull()
    expect(archivePartsTotalBytes([{ size_bytes: Number.MAX_SAFE_INTEGER }, { size_bytes: 1 }])).toBeNull()
  })

  it('falls back to the existing minimum for missing or invalid inputs', () => {
    expect(unifiedExportRequestTimeoutMs(null)).toBe(UNIFIED_EXPORT_REQUEST_TIMEOUT_MS)
    expect(unifiedExportRequestTimeoutMs(Number.NaN)).toBe(UNIFIED_EXPORT_REQUEST_TIMEOUT_MS)
    expect(unifiedExportRequestTimeoutMs(1.5)).toBe(UNIFIED_EXPORT_REQUEST_TIMEOUT_MS)
    expect(unifiedExportRequestTimeoutMs(Number.MAX_SAFE_INTEGER + 1)).toBe(
      UNIFIED_EXPORT_REQUEST_TIMEOUT_MS,
    )
  })

  it('covers a 45 GB HDD copy plus orchestration grace', () => {
    expect(unifiedExportRequestTimeoutMs(45_000_000_000)).toBe(450_600_000)
  })

  it('does not let a small known export undercut the existing minimum', () => {
    expect(unifiedExportRequestTimeoutMs(1_000)).toBe(UNIFIED_EXPORT_REQUEST_TIMEOUT_MS)
  })

  it('caps abnormal inputs at the bounded request maximum', () => {
    expect(unifiedExportRequestTimeoutMs(500_000_000_000)).toBe(
      UNIFIED_EXPORT_MAX_REQUEST_TIMEOUT_MS,
    )
  })

  it('uses a 30-day maximum that remains representable by XMLHttpRequest', () => {
    expect(UNIFIED_EXPORT_MAX_REQUEST_TIMEOUT_MS).toBe(30 * 24 * 60 * 60 * 1000)
    expect(UNIFIED_EXPORT_MAX_REQUEST_TIMEOUT_MS).toBeLessThan(2 ** 32)
  })
})
