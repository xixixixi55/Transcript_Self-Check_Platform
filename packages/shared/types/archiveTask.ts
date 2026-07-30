import type {
  ArchiveProgressKind,
  ArchiveTaskAction,
  ArchiveWorkerState,
  TaskStatus,
} from './task'

export type ArchiveWorkflowStage =
  | 'queued'
  | 'inventory'
  | 'preflight_verified'
  | 'winrar'
  | 'integrity'
  | 'integrity_verified'
  | 'md5'
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

export interface ReconciledVolumeSlots {
  active_slots: VolumeSlot[]
  removed_slots: VolumeSlot[]
}

export interface VerifiedVolumeSlot {
  slot_id: string
  ordinal: number
  disc_number: string
  output_bytes: number
  md5: string
}
