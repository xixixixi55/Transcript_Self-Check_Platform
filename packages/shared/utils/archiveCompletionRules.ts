// Layer 2: SharedUtils — archive completion state projection (pure).

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
