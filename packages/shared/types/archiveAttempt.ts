import type { ArchiveDecision, ArchiveDecisionStatus, CaseDetail, WorkbenchSchemaVersion } from './workbench'
import type { ArchiveTaskPublicDetail } from './archiveTask'

export type ArchiveAttemptStatus = 'accepted' | 'running' | 'succeeded' | 'failed' | 'interrupted'
export type ArchiveCleanupStatus = 'not_required' | 'pending' | 'succeeded' | 'failed' | 'unknown'

/** Public, path-free view of the Phase 1D archive attempt record. */
export interface ArchiveAttemptRecord {
  schema_version: WorkbenchSchemaVersion
  attempt_id: string
  case_id: string
  source_id: string
  input_revision: number
  status: ArchiveAttemptStatus
  cleanup_status: ArchiveCleanupStatus
  error_code?: string | null
  manifest_id?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  revision: number
}

export interface ArchiveDecisionResult {
  case: CaseDetail
  decision: ArchiveDecision
  archive_status: ArchiveDecisionStatus
  archive_context_id: string | null
  archive_attempt_id?: string | null
  archive_task?: ArchiveTaskPublicDetail | null
}
