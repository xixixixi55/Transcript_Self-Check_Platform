import { RETENTION_DEFAULTS, RETENTION_POLICY_MODES } from '../constants'
import type { RetentionPolicyMode } from '../types'

const UTC_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]00:00)$/

export function isRetentionPolicyMode(value: unknown): value is RetentionPolicyMode {
  return typeof value === 'string' && RETENTION_POLICY_MODES.includes(value as RetentionPolicyMode)
}
export function isUtcIsoTimestamp(value: unknown): value is string {
  if (typeof value !== 'string' || !UTC_TIMESTAMP.test(value)) return false
  const parsed = Date.parse(value)
  return Number.isFinite(parsed)
}

export function isTrustedUtcTimestamp(value: unknown, nowMs = Date.now()): value is string {
  if (!isUtcIsoTimestamp(value)) return false
  const timestampMs = Date.parse(value)
  return timestampMs <= nowMs + RETENTION_DEFAULTS.future_clock_skew_seconds * 1000
}

export function expiresAtUtc(anchor: string, retentionDays: number, nowMs = Date.now()): string {
  if (!isUtcIsoTimestamp(anchor)) throw new Error('RETENTION_TIME_INVALID')
  if (!isTrustedUtcTimestamp(anchor, nowMs)) throw new Error('RETENTION_TIME_IN_FUTURE')
  if (!Number.isSafeInteger(retentionDays)
    || retentionDays < RETENTION_DEFAULTS.minimum_days
    || retentionDays > RETENTION_DEFAULTS.maximum_days) {
    throw new Error('INVALID_RETENTION_DAYS')
  }
  return new Date(Date.parse(anchor) + retentionDays * 24 * 60 * 60 * 1000).toISOString()
}
