export type ArchiveVolumeTier = '4GB' | '22GB' | '45GB'
export type ArchivePlanStatus = 'planned' | 'blocked'
export type ArchiveValidationStatus = 'validated' | 'invalid'
export type ArchiveExecutionStatus =
  | 'idle'
  | 'planning'
  | 'blocked'
  | 'compressing'
  | 'validating'
  | 'hashing'
  | 'completed'
  | 'failed'

export interface ArchiveContextSummary {
  archive_context_id: string
  file_count: number
  total_input_bytes: number
  status: ArchiveExecutionStatus
  created_at: string
  expires_at: string
}

export interface ArchiveSourceEntry {
  relative_path: string
  size_bytes: number
  modified_time_ns: number
}

export interface ArchiveDiagnostic {
  code: string
  message: string
}

export interface ArchiveCapability {
  available: boolean
  executable_name: 'WinRAR.exe' | 'rar.exe' | null
  version: string | null
  supports_rar_volumes: boolean
}

export interface ArchivePlan {
  plan_id: string
  case_display_name: string
  archive_base_name: string
  source_entries: ArchiveSourceEntry[]
  total_input_bytes: number
  volume_size_bytes: number
  volume_tier_gb: number
  expected_part_count: number
  max_part_count: number
  first_disc_number: string | null
  expected_disc_numbers: string[]
  max_replan_attempts: number
  status: ArchivePlanStatus
  diagnostics: ArchiveDiagnostic[]
}

export interface ArchivePart {
  part_id: string
  part_number: number
  filename: string
  size_bytes: number
  md5: string
  disc_number: string
  disc_date: string
  volume_size_bytes: number
  continuity_check: 'passed'
}

export interface ArchiveManifest {
  manifest_id: string
  plan_id: string
  archive_base_name: string
  volume_size_bytes: number
  volume_tier_gb: number
  total_input_bytes: number
  actual_archive_bytes: number
  retry_count: number
  parts: ArchivePart[]
  created_at: string
  winrar_capability: ArchiveCapability
  validation_status: ArchiveValidationStatus
  continuity_check: 'passed'
}

export interface ArchiveExecutionResponse {
  status: ArchiveExecutionStatus
  manifest_id: string | null
  plan: ArchivePlan | null
  diagnostics: ArchiveDiagnostic[]
}
