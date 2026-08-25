// Layer 2: SharedUtils — archive completion state projection (pure).

import {
  UNIFIED_EXPORT_HDD_MIN_THROUGHPUT_BYTES_PER_SECOND,
  UNIFIED_EXPORT_MAX_REQUEST_TIMEOUT_MS,
  UNIFIED_EXPORT_ORCHESTRATION_GRACE_MS,
  UNIFIED_EXPORT_REQUEST_TIMEOUT_MS,
} from '../constants'
import type { ArchiveCompletionStatus, CaseLifecycle } from '../types'

/**
 * Project the card-level archive completion state from lifecycle plus whether
 * every RAR part carries a disc number. Not a lifecycle value itself.
 */
export function resolveArchiveCompletionStatus(
  lifecycle: CaseLifecycle,
  allDiscMapped: boolean,
): ArchiveCompletionStatus | null {
  if (lifecycle === 'exported') return 'exported'
  if (lifecycle === 'archive_verified') {
    return allDiscMapped ? 'archive_complete' : 'disc_pending'
  }
  if (lifecycle === 'archiving' || lifecycle === 'archive_queued') return 'compressing'
  return null
}

/** True when every part carries a non-empty disc number. */
export function allPartsDiscMapped(
  parts: { disc_number?: string | null }[] | null | undefined,
): boolean {
  return !!parts && parts.length > 0 && parts.every(part => !!part.disc_number)
}

/** Sum verified part sizes, returning null when the evidence is incomplete. */
export function archivePartsTotalBytes(
  parts: { size_bytes?: number | null }[] | null | undefined,
): number | null {
  if (!parts?.length) return null
  let total = 0
  for (const part of parts) {
    const size = part.size_bytes
    if (typeof size !== 'number' || !Number.isSafeInteger(size) || size <= 0) return null
    total += size
  }
  return Number.isSafeInteger(total) && total > 0 ? total : null
}

/**
 * Bound the synchronous export request for one HDD staging-copy pass plus
 * orchestration grace. HashMyFiles is not part of inspection-record export.
 */
export function unifiedExportRequestTimeoutMs(
  totalArchiveBytes: number | null | undefined,
): number {
  if (
    typeof totalArchiveBytes !== 'number'
    || !Number.isSafeInteger(totalArchiveBytes)
    || totalArchiveBytes <= 0
  ) return UNIFIED_EXPORT_REQUEST_TIMEOUT_MS
  const copyPassMilliseconds = Math.ceil(
    (totalArchiveBytes * 1000)
    / UNIFIED_EXPORT_HDD_MIN_THROUGHPUT_BYTES_PER_SECOND,
  )
  return Math.min(
    UNIFIED_EXPORT_MAX_REQUEST_TIMEOUT_MS,
    Math.max(
      UNIFIED_EXPORT_REQUEST_TIMEOUT_MS,
      copyPassMilliseconds
        + UNIFIED_EXPORT_ORCHESTRATION_GRACE_MS,
    ),
  )
}
