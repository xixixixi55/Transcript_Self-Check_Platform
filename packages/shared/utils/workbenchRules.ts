import type { CaseLifecycle, DualSaveResult, FieldConfirmation, FieldSource, SaveStatus } from '../types'
import { REVIEWABLE_CASE_LIFECYCLES } from '../constants'

export interface InitialFieldValue<T> {
  value: T | null
  source: FieldSource
  confirmation: FieldConfirmation
}

export function resolveInitialFieldValue<T>(reportValue: T | null | undefined, defaultValue: T | null | undefined): InitialFieldValue<T> {
  if (reportValue !== null && reportValue !== undefined && String(reportValue).trim() !== '') {
    return { value: reportValue, source: 'report', confirmation: 'confirmed' }
  }
  if (defaultValue !== null && defaultValue !== undefined && String(defaultValue).trim() !== '') {
    return { value: defaultValue, source: 'system_default', confirmation: 'confirmed' }
  }
  return { value: null, source: 'system_default', confirmation: 'pending' }
}

export function markUserEdited<T>(state: InitialFieldValue<T>, value: T): InitialFieldValue<T> {
  return { ...state, value, source: 'user' }
}

const TRANSITIONS: Record<CaseLifecycle, readonly CaseLifecycle[]> = {
  case_created: ['parse_queued', 'cancelling'],
  parse_queued: ['parsing', 'parse_failed_retryable', 'cancelling'],
  parsing: ['review_ready', 'parse_failed_retryable', 'cancelling'],
  review_ready: ['archive_deferred', 'archive_queued', 'exporting_word', 'cancelling'],
  parse_failed_retryable: ['parse_queued', 'cancelling'],
  archive_deferred: ['archive_queued', 'exporting_word', 'cancelling'],
  archive_queued: ['archiving', 'cancelling'],
  archiving: ['archive_verified', 'archive_deferred', 'cancelling'],
  archive_verified: ['exporting_word', 'cancelling'],
  exporting_word: ['exported', 'archive_verified', 'cancelling'],
  exported: ['record_retention_expired'],
  record_retention_expired: ['record_cleaned'],
  record_cleaned: [],
  cancelling: ['cancelled'],
  cancelled: ['parse_queued', 'archive_queued'],
}

export function isLegalCaseLifecycleTransition(from: CaseLifecycle, to: CaseLifecycle): boolean {
  return TRANSITIONS[from].includes(to)
}

export function isReviewableCaseLifecycle(lifecycle: CaseLifecycle): boolean {
  return REVIEWABLE_CASE_LIFECYCLES.includes(lifecycle)
}

export function isRevisionCurrent(expectedRevision: number, actualRevision: number): boolean {
  return Number.isInteger(expectedRevision) && expectedRevision === actualRevision
}

export function aggregateDualSaveResult(draft: SaveStatus, defaults: SaveStatus): DualSaveResult {
  return { draft_save_status: draft, shared_defaults_save_status: defaults }
}

export function isUnauthenticatedClientIdentity(identity: { identity_kind: string }): boolean {
  return identity.identity_kind === 'local_session'
}
