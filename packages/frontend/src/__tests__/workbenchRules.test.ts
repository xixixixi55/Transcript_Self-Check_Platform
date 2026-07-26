import { describe, expect, it } from 'vitest'
import {
  aggregateDualSaveResult,
  isLegalCaseLifecycleTransition,
  isRevisionCurrent,
  isReviewableCaseLifecycle,
  isUnauthenticatedClientIdentity,
  markUserEdited,
  resolveInitialFieldValue,
} from '@biji/shared/utils'

describe('workbench pure rules', () => {
  it('prefers a valid report value over a shared default', () => {
    expect(resolveInitialFieldValue('SYNTHETIC-REPORT', 'SYNTHETIC-DEFAULT')).toEqual({
      value: 'SYNTHETIC-REPORT', source: 'report', confirmation: 'confirmed',
    })
  })

  it('uses a shared default only when the report value is empty', () => {
    expect(resolveInitialFieldValue('', 'SYNTHETIC-DEFAULT')).toEqual({
      value: 'SYNTHETIC-DEFAULT', source: 'system_default', confirmation: 'confirmed',
    })
    expect(resolveInitialFieldValue(null, null)).toEqual({
      value: null, source: 'system_default', confirmation: 'pending',
    })
  })

  it('moves a field to user source without changing confirmation', () => {
    const state = resolveInitialFieldValue('SYNTHETIC-REPORT', 'SYNTHETIC-DEFAULT')
    expect(markUserEdited(state, 'SYNTHETIC-USER')).toEqual({
      value: 'SYNTHETIC-USER', source: 'user', confirmation: 'confirmed',
    })
  })

  it('enforces lifecycle and revision rules', () => {
    expect(isLegalCaseLifecycleTransition('case_created', 'parse_queued')).toBe(true)
    expect(isLegalCaseLifecycleTransition('parse_failed_retryable', 'review_ready')).toBe(false)
    expect(isReviewableCaseLifecycle('review_ready')).toBe(true)
    expect(isReviewableCaseLifecycle('parse_failed_retryable')).toBe(false)
    expect(isRevisionCurrent(2, 2)).toBe(true)
    expect(isRevisionCurrent(2, 3)).toBe(false)
  })

  it('keeps separate results for the two default writes and identifies local sessions', () => {
    expect(aggregateDualSaveResult({ status: 'saved' }, { status: 'failed', error_code: 'SYNTHETIC_ERROR' })).toEqual({
      draft_save_status: { status: 'saved' },
      shared_defaults_save_status: { status: 'failed', error_code: 'SYNTHETIC_ERROR' },
    })
    expect(isUnauthenticatedClientIdentity({ identity_kind: 'local_session' })).toBe(true)
  })
})
