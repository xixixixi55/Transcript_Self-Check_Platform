import type {
  ArchiveProgressKind,
  ArchiveTaskAction,
  ArchiveWorkerState,
  TaskStatus,
} from './task'
import type { ArchiveMedium, ArchiveMode, ArchivePartHash } from './archive'

export type ArchiveWorkflowStage =
  | 'queued'
  | 'inventory'
  | 'preflight_verified'
  | 'winrar'
  | 'integrity'
  | 'integrity_verified'
  | 'hash'
  | 'manifest'
  | 'completed'

export type ArchiveWorkflowMilestonePercent = 0 | 10 | 20 | 30 | 75 | 85 | 90 | 95 | 100
export type VolumeSlotStatus = 'active' | 'pending' | 'removed' | 'verified'
export type DiscMappingSource = 'default' | 'user'
export type DiscMappingConfirmation = 'confirmed' | 'pending'

export interface DiscMapping {
  slot_id: string
  disc_number: string
  disc_date: string
  source: DiscMappingSource
  confirmation: DiscMappingConfirmation
}

export interface VolumeSlot {
  slot_id: string
  ordinal: number
  plan_revision: number
  lineage_key: string
  planned_input_bytes: number
  status: VolumeSlotStatus
  disc_mapping: DiscMapping | null
}

export interface PlannedVolumeSlot {
  ordinal: number
  lineage_key: string
  planned_input_bytes: number
}

export interface ArchivePlanSnapshot {
  plan_id: string
  case_id: string
  plan_revision: number
  input_inventory_revision: number
  mapping_revision: number
  volume_slots: VolumeSlot[]
  created_at: string
  updated_at: string
}

export interface ProgressSnapshot {
  progress_kind: ArchiveProgressKind
  stage: ArchiveWorkflowStage
  stage_label: string
  stage_index: number
  stage_count: number
  percent: ArchiveWorkflowMilestonePercent
  updated_at: string
  last_heartbeat_at: string | null
  output_bytes: number | null
  output_volume_count: number | null
  last_output_change_at: string | null
  worker_state: ArchiveWorkerState
}

export interface ArchiveTaskCardSummary extends ProgressSnapshot {
  task_id: string
  case_id: string
  status: TaskStatus
  started_at: string | null
  finished_at: string | null
  error_summary: string | null
  allowed_actions: ArchiveTaskAction[]
}

export type LegacyArchiveCompatibilityStatus =
  | 'legacy_explicit_available'
  | 'legacy_explicit_running'
  | 'legacy_explicit_interrupted'

export type ResourceAdmissionStatus = 'admitted' | 'queued' | 'blocked'

export interface ArchiveResourceAdmission {
  status: ResourceAdmissionStatus
  reason_code: string | null
  evaluated_at: string
}

export interface ArchiveTaskCommandRequest {
  expected_revision: number
}

export interface ArchiveTaskCommandResult {
  task_id: string
  status: TaskStatus
  allowed_actions: ArchiveTaskAction[]
}

export interface ArchiveTaskPublicDetail extends ArchiveTaskCardSummary {
  created_at: string
  revision: number
  attempt: number
  cancel_requested: boolean
  error_code: string | null
  archive_plan: ArchivePlanSnapshot | null
}

export interface ArchiveTaskHistory {
  case_id: string
  items: ArchiveTaskPublicDetail[]
}

export type ArchiveTaskResultPart = {
  part_id: string
  filename: string
  size_bytes: number
  disc_number: string
  disc_date: string
} & ArchivePartHash

export interface ArchiveTaskResult {
  task_id: string
  case_id: string
  manifest_id: string
  archive_mode: ArchiveMode
  archive_medium: ArchiveMedium
  /** 更新持久化归档计划的乐观并发令牌。 */
  plan_row_revision: number | null
  verified_slots: VerifiedVolumeSlot[]
  assets: {
    asset_id: string
    case_id: string
    task_id: string | null
    plan_id: string | null
    asset_kind: 'staging' | 'rar_volume' | 'manifest'
    status: 'published' | 'verified'
    created_at: string
    updated_at: string
    revision: number
  }[]
  parts: ArchiveTaskResultPart[]
  finished_at: string | null
}

export interface ReconciledVolumeSlots {
  active_slots: VolumeSlot[]
  removed_slots: VolumeSlot[]
}

export type VerifiedVolumeSlot = {
  slot_id: string
  ordinal: number
  disc_number: string
  output_bytes: number
} & ArchivePartHash
