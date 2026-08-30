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
  | 'queued'
  | 'parse'
  | 'inventory'
  | 'planning'
  | 'preflight_verified'
  | 'winrar'
  | 'integrity'
  | 'integrity_verified'
  | 'hash'
  | 'manifest'
  | 'completed'
  | 'export'
  | 'cleanup'
  | 'none'

export type ArchiveProgressKind = 'workflow_milestone'
export type ArchiveWorkerState =
  | 'unassigned'
  | 'starting'
  | 'owned_running'
  | 'recovering'
  | 'waiting_reclaim'
  | 'released'
export type ArchiveTaskAction = 'cancel' | 'retry' | 'view_result' | 'view_details'

export interface TaskRecord {
  schema_version: 1
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
  updated_at?: string
  finished_at?: string | null
  progress_kind?: ArchiveProgressKind | null
  stage_label?: string
  stage_index?: number
  stage_count?: number
  last_heartbeat_at?: string | null
  output_bytes?: number | null
  output_volume_count?: number | null
  last_output_change_at?: string | null
  worker_state?: ArchiveWorkerState | null
  allowed_actions?: ArchiveTaskAction[]
  revision: number
}
