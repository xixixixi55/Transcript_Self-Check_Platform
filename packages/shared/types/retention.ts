/** Public retention and formal-artifact contracts.
 *
 * These DTOs deliberately contain stable case/publication/artifact identities
 * only. Internal paths, database names, attempt/context identities, claims,
 * leases and fences stay in the backend persistence layer.
 */

export type RetentionPolicyMode = 'disabled' | 'preview_only' | 'enforce'
export type RetentionEligibility = 'eligible' | 'ineligible' | 'unknown'
export type RetentionStatus =
  | 'unknown'
  | 'not_expired'
  | 'eligible'
  | 'blocked'
  | 'planned'
  | 'processing'
  | 'completed'
  | 'failed'

export type CleanupRunPhase =
  | 'planned'
  | 'claimed'
  | 'preflighted'
  | 'work_files_cleaned'
  | 'records_cleaned'
  | 'verified'
  | 'succeeded'
  | 'blocked'
  | 'stale'
  | 'cancel_requested'
  | 'cancelled'
  | 'interrupted'
  | 'partial_failure'
  | 'failed_retryable'
  | 'failed_terminal'

export type CleanupRunStatus = 'active' | 'succeeded' | 'cancelled' | 'failed' | 'blocked'

export type RetentionBlockerCode =
  | 'RETENTION_CASE_MUTATION_TIME_MISSING'
  | 'RETENTION_PUBLICATION_MISSING'
  | 'RETENTION_PUBLICATION_UNVERIFIED'
  | 'RETENTION_PUBLICATION_TIME_MISSING'
  | 'RETENTION_WORD_ARTIFACT_MISSING'
  | 'RETENTION_WORD_ARTIFACT_UNVERIFIED'
  | 'RETENTION_TIME_INVALID'
  | 'RETENTION_TIME_IN_FUTURE'
  | 'RETENTION_NOT_EXPIRED'
  | 'RETENTION_ACTIVE_TASK'
  | 'RETENTION_ACTIVE_LEASE'
  | 'RETENTION_RECOVERY_IN_PROGRESS'
  | 'RETENTION_OWNERSHIP_UNKNOWN'
  | 'RETENTION_AUTHORITY_INCONSISTENT'
  | 'RETENTION_SNAPSHOT_ACTIVE'
  | 'RETENTION_SNAPSHOT_RECOVERY_REFERENCED'
  | 'RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN'

export type CleanupErrorCode =
  | 'CLEANUP_PATH_OUTSIDE_ALLOWED_ROOT'
  | 'CLEANUP_OWNERSHIP_UNKNOWN'
  | 'CLEANUP_SYMLINK_OR_JUNCTION_REJECTED'
  | 'CLEANUP_FILE_IN_USE'
  | 'CLEANUP_ACCESS_DENIED'
  | 'CLEANUP_FILE_CHANGED'
  | 'CLEANUP_FILE_DELETE_FAILED'
  | 'CLEANUP_SNAPSHOT_DELETE_FAILED'
  | 'CLEANUP_STALE_REQUEST'
  | 'CLEANUP_CONFLICT'

export interface RetentionPolicyDto {
  mode: RetentionPolicyMode
  retention_days: number
  scan_interval_seconds: number
  batch_size: number
  policy_revision: number
  activated_at: string | null
  updated_at: string
}

export interface RetentionStatusDto {
  case_id: string
  status: RetentionStatus
  eligibility: RetentionEligibility
  retention_anchor_utc: string | null
  expires_at_utc: string | null
  blocker_code: RetentionBlockerCode | null
  policy_revision: number
  case_revision: number
  updated_at: string
}

export interface CleanupPreviewItemDto {
  case_id: string
  eligibility: RetentionEligibility
  blocker_code: RetentionBlockerCode | null
  planned_data_categories: string[]
  preserved_formal_artifact_categories: string[]
  retention_anchor_utc: string | null
  expires_at_utc: string | null
  has_running_task: boolean
  has_edit_lease: boolean
  has_recovery: boolean
  has_conflict: boolean
}

export interface CleanupPreviewDto {
  policy: RetentionPolicyDto
  items: CleanupPreviewItemDto[]
  generated_at: string
}

export interface CleanupRunStatusDto {
  run_id: string
  case_id: string
  phase: CleanupRunPhase
  status: CleanupRunStatus
  result_code: string | null
  error_code: CleanupErrorCode | null
  updated_at: string
  completed_at: string | null
}

export interface FormalWordArtifactSafeProjection {
  word_artifact_id: string
  case_id: string
  publication_id: string
  file_digest: string
  file_size: number
  source_manifest_digest: string
  template_identity: string
  template_version: string
  generated_at: string
  verified_at: string | null
  status: 'pending' | 'verified' | 'invalid'
}
