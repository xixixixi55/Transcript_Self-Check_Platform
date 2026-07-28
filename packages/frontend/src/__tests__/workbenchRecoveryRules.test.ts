import { describe, expect, it } from 'vitest'
import {
  hasSafeArchiveAttemptPublicFields,
  isLegalCaseLifecycleTransition,
  isTerminalArchiveAttempt,
} from '@biji/shared/utils'

describe('Phase 1D recovery rules', () => {
  it('allows archive_interrupted to leave only through explicit user decisions', () => {
    expect(isLegalCaseLifecycleTransition('archive_queued', 'archive_interrupted')).toBe(true)
    expect(isLegalCaseLifecycleTransition('archiving', 'archive_interrupted')).toBe(true)
    expect(isLegalCaseLifecycleTransition('archive_interrupted', 'archive_deferred')).toBe(true)
    expect(isLegalCaseLifecycleTransition('archive_interrupted', 'archive_queued')).toBe(true)
    expect(isLegalCaseLifecycleTransition('archive_interrupted', 'archiving')).toBe(false)
    expect(isLegalCaseLifecycleTransition('archive_interrupted', 'archive_verified')).toBe(false)
  })

  it('keeps pending source review separate from the archive lifecycle', () => {
    expect(isLegalCaseLifecycleTransition('review_ready', 'archive_interrupted')).toBe(false)
  })

  it('keeps succeeded attempts terminal and public records path-free', () => {
    expect(isTerminalArchiveAttempt('succeeded')).toBe(true)
    expect(isTerminalArchiveAttempt('accepted')).toBe(false)
    expect(hasSafeArchiveAttemptPublicFields({ attempt_id: 'SYNTHETIC-ATTEMPT-001', status: 'succeeded' })).toBe(true)
    expect(hasSafeArchiveAttemptPublicFields({ attempt_id: 'SYNTHETIC-ATTEMPT-001', staging_locator: 'C:\\private' })).toBe(false)
    expect(hasSafeArchiveAttemptPublicFields({ attempt_id: 'SYNTHETIC-ATTEMPT-001', process_pid: 42 })).toBe(false)
  })
})
