import type { DocumentNumberTemplate, InspectionReport } from './index'
import type { ArchiveTaskCardSummary } from './archiveTask'
import type { TaskRecord } from './task'
import type { TemplateVersionRef } from './template'
import type { HashAlgorithm } from './hash'

export type WorkbenchSchemaVersion = 1
export type WorkbenchApiVersion = 'v1'

export type CaseLifecycle =
  | 'case_created'
  | 'parse_queued'
  | 'parsing'
  | 'review_ready'
  | 'parse_failed_retryable'
  | 'archive_deferred'
  | 'archive_interrupted'
  | 'archive_queued'
  | 'archiving'
  | 'archive_verified'
  | 'exporting_word'
  | 'exported'
  | 'record_retention_expired'
  | 'record_cleaned'
  | 'cancelling'
  | 'cancelled'

export type FieldSource = 'report' | 'user' | 'system_default'
export type FieldConfirmation = 'confirmed' | 'pending'
export type LeaseStatus = 'active' | 'released' | 'expired'
export type SourceAccessStatus = 'pending' | 'available' | 'invalid' | 'requires_reselection'
export type ArchiveDecision = 'immediate' | 'deferred'
export type ArchiveDecisionStatus = 'archive_task_queued' | 'deferred'

export interface OpaqueAssetRef {
  asset_id: string
  asset_kind: 'image' | 'source_snapshot' | 'cache' | 'staging' | 'other'
  fingerprint?: string
  metadata?: Record<string, string | number | boolean>
}

export type CaseAssetContentStatus = 'available' | 'missing' | 'corrupt'

export interface CaseAssetRecord extends OpaqueAssetRef {
  content_status: CaseAssetContentStatus
}

export interface CaseAssetList {
  items: CaseAssetRecord[]
}

export interface CasePhotoBindingRequest {
  asset_refs: OpaqueAssetRef[]
  expected_asset_ids: string[]
  lease_id: string
  lease_token: string
}

export interface CasePhotoBindingResult {
  draft: CaseDraft
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
  archive_task_summary?: ArchiveTaskCardSummary | null
  last_unified_export_at?: string | null
  /** 案件列表从既有草稿报告投影的只读委托信息。 */
  entrust_unit?: string
  entrust_persons?: string[]
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
  template_ref?: TemplateVersionRef | null
  archive_plan_id?: string | null
  lifecycle: CaseLifecycle
  revision: number
  created_at: string
  updated_at: string
}

export interface SharedDefaults {
  schema_version: WorkbenchSchemaVersion
  deployment_instance_id: string
  revision: number
  /** 为兼容持久化部署而保留的旧版完整值默认项。 */
  document_number: string
  /** 快照到后续新案件中的格式；序号仍限定在案件范围内。 */
  document_number_template?: DocumentNumberTemplate
  inspection_place: string
  inspection_method: string
  hardware_device: string
  inspector_order: string[]
  /** 后续新案件的默认值；旧版部署可能省略。 */
  inspection_requirement?: string
  /** 仅为兼容持久化部署而保留；设置页面不再编辑。 */
  extraction_method?: string
  /** 后续新案件的默认值；旧版部署可能省略。 */
  data_summary?: string
  /** 为兼容旧版迁移而保留在 API 中；设置页面不再编辑。 */
  disc_number_prefix: string
  /** 旧版部署省略时默认为 MD5。 */
  hash_algorithm?: HashAlgorithm
  default_template_ref?: TemplateVersionRef | null
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
  revalidation_error_code?: string | null
  last_verified_at?: string | null
  revision: number
}

export interface SaveStatus {
  status: 'saved' | 'conflict' | 'failed'
  revision?: number
  error_code?: string
}
export interface SharedDefaultsSaveStatus {
  status: 'updated' | 'unchanged' | 'failed' | 'revision_conflict'
  revision?: number
  error_code?: string
}
export interface DualSaveResult {
  draft_save_status: SaveStatus
  shared_defaults_save_status: SharedDefaultsSaveStatus
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
  shared_defaults: SharedDefaults
}

export interface DirectorySelectionCancelled {
  cancelled: true
}

export type CaseDirectorySubmissionResult = CaseSubmission | DirectorySelectionCancelled

export interface DeletePreflight {
  allowed: boolean
  blockers: string[]
}

export interface CaseDeletionResult {
  case_id: string
  deleted: true
}

export interface CaseListResponse extends WorkbenchApiEnvelope<CaseListPage> {}
export interface CaseDetailResponse extends WorkbenchApiEnvelope<CaseDetail> {}
export interface CaseSubmissionResponse extends WorkbenchApiEnvelope<CaseSubmission> {}
export interface CaseDirectorySubmissionResponse extends WorkbenchApiEnvelope<CaseDirectorySubmissionResult> {}
