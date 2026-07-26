import type { InspectionReport } from './index'

export type WorkbenchSchemaVersion = 1
export type WorkbenchApiVersion = 'v1'

export type CaseLifecycle =
  | 'case_created'
  | 'parse_queued'
  | 'parsing'
  | 'review_ready'
  | 'parse_failed_retryable'
  | 'archive_deferred'
  | 'archive_queued'
  | 'archiving'
  | 'archive_verified'
  | 'exporting_word'
  | 'exported'
  | 'record_retention_expired'
  | 'record_cleaned'
  | 'cancelling'
  | 'cancelled'

export type TaskKind = 'parse' | 'archive' | 'export_word' | 'cleanup'
export type TaskStatus =
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'interrupted'
  | 'succeeded'
  | 'failed_retryable'
  | 'failed_terminal'
  | 'cancelled'
  | 'blocked'
export type TaskStage =
  | 'parse'
  | 'inventory'
  | 'planning'
  | 'winrar'
  | 'integrity'
  | 'md5'
  | 'manifest'
  | 'export'
  | 'cleanup'
  | 'none'

export type FieldSource = 'report' | 'user' | 'system_default'
export type FieldConfirmation = 'confirmed' | 'pending'
export type LeaseStatus = 'active' | 'released' | 'expired'
export type SourceAccessStatus = 'pending' | 'available' | 'invalid' | 'requires_reselection'

export interface OpaqueAssetRef {
  asset_id: string
  asset_kind: 'image' | 'source_snapshot' | 'cache' | 'staging' | 'other'
  fingerprint?: string
  metadata?: Record<string, string | number | boolean>
}

export interface FieldState {
  field_path: string
  subject_id?: string
  source: FieldSource
  confirmation: FieldConfirmation
  revision: number
  last_changed_at: string
}

export interface CaseShell {
  schema_version: WorkbenchSchemaVersion
  case_id: string
  case_number?: string
  case_name: string
  case_summary: string
  source_id: string
  parse_task_id: string
  lifecycle: CaseLifecycle
  report_available: boolean
  revision: number
  created_at: string
  updated_at: string
}

export interface CaseDraft {
  schema_version: WorkbenchSchemaVersion
  case_id: string
  case_number?: string
  case_name: string
  case_summary: string
  report: InspectionReport
  report_version: string
  field_states: Record<string, FieldState>
  asset_refs: OpaqueAssetRef[]
  template_ref?: { template_id: string; version: string } | null
  archive_plan_id?: string | null
  lifecycle: Extract<CaseLifecycle, 'review_ready' | 'archive_deferred' | 'archive_queued' | 'archiving' | 'archive_verified' | 'exporting_word' | 'exported'>
  revision: number
  created_at: string
  updated_at: string
}

export interface SharedDefaults {
  schema_version: WorkbenchSchemaVersion
  deployment_instance_id: string
  revision: number
  document_number: string
  inspection_place: string
  inspection_method: string
  hardware_device: string
  inspector_order: string[]
  disc_number_prefix: string
  migration_decision: 'pending' | 'imported' | 'ignored'
  updated_at: string
}

export interface ClientIdentity {
  client_instance_id: string
  session_id: string
  local_display_name?: string
  deployment_instance_id: string
  observed_at: string
  identity_kind: 'local_session'
}

export interface EditLease {
  schema_version: WorkbenchSchemaVersion
  lease_id: string
  case_id: string
  session_id: string
  client_instance_id: string
  lease_token: string
  last_heartbeat_at: string
  expires_at: string
  status: LeaseStatus
  takeover_of_lease_id?: string | null
  revision: number
}

export interface TaskRecord {
  schema_version: WorkbenchSchemaVersion
  task_id: string
  case_id: string
  kind: TaskKind
  status: TaskStatus
  stage: TaskStage
  percent: number | null
  counters: Record<string, number>
  input_revision: number
  attempt: number
  process_binding?: { process_tree_id: string; staging_asset_id?: string } | null
  error_code?: string | null
  error_summary?: string | null
  cancel_requested: boolean
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  revision: number
}

export interface SourceRecord {
  schema_version: WorkbenchSchemaVersion
  source_id: string
  source_type: 'report_directory' | 'report_archive' | 'uploaded_file' | 'other'
  case_id: string
  task_id?: string | null
  allowed_root_id: string
  metadata: Record<string, string | number | boolean>
  fingerprint: string
  access_status: SourceAccessStatus
  requires_reselection: boolean
  last_verified_at?: string | null
  revision: number
}

export interface SaveStatus {
  status: 'saved' | 'conflict' | 'failed'
  revision?: number
  error_code?: string
}

export interface DualSaveResult {
  draft_save_status: SaveStatus
  shared_defaults_save_status: SaveStatus
}

export interface RevisionConflictDto {
  error_code: 'REVISION_CONFLICT'
  resource: 'case_draft' | 'shared_defaults' | 'task' | 'lease'
  expected_revision: number
  actual_revision: number
}

export interface WorkbenchApiEnvelope<T> {
  api_version: WorkbenchApiVersion
  schema_version: WorkbenchSchemaVersion
  data: T
}

export interface CaseShellResponse extends WorkbenchApiEnvelope<CaseShell> {}
export interface CaseDraftResponse extends WorkbenchApiEnvelope<CaseDraft> {}
export interface SourceRecordResponse extends WorkbenchApiEnvelope<SourceRecord> {}
export interface SharedDefaultsResponse extends WorkbenchApiEnvelope<SharedDefaults> {}
export interface TaskRecordResponse extends WorkbenchApiEnvelope<TaskRecord> {}

export interface CaseListPage {
  items: CaseShell[]
  offset: number
  limit: number
  has_more: boolean
}

export interface CaseDetail {
  shell: CaseShell
  draft: CaseDraft | null
  source: SourceRecord
  parse_task: TaskRecord
}

export interface CaseSubmission {
  shell: CaseShell
  source: SourceRecord
  parse_task: TaskRecord
}

export interface DeletePreflight {
  allowed: boolean
  blockers: string[]
}

export interface CaseListResponse extends WorkbenchApiEnvelope<CaseListPage> {}
export interface CaseDetailResponse extends WorkbenchApiEnvelope<CaseDetail> {}
export interface CaseSubmissionResponse extends WorkbenchApiEnvelope<CaseSubmission> {}
