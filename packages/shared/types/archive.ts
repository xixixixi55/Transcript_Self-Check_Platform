import type { HashAlgorithm } from './hash'

export type ArchiveVolumeTier = '4GB' | '22GB' | '45GB'
export type ArchiveMode = 'standard_split' | 'oversized_single_volume'
export type ArchiveMedium = 'optical_disc' | 'hard_drive'
export type ArchivePlanStatus = 'planned' | 'blocked'
export type ArchiveValidationStatus = 'validated' | 'invalid'
export type ArchiveExecutionStatus =
  | 'idle'
  | 'waiting'
  | 'planning'
  | 'blocked'
  | 'compressing'
  | 'validating'
  | 'hashing'
  | 'completed'
  | 'failed'

export type ArchivePreparationStatus = 'not_prepared' | 'preparing' | 'ready' | 'failed'
export type ArchiveContextKind = 'preview_source' | 'formal'
export type ArchiveLifecycleStatus = ArchiveExecutionStatus | ArchivePreparationStatus

export interface ArchiveContextSummary {
  archive_context_id: string
  file_count: number | null
  total_input_bytes: number | null
  status: ArchiveLifecycleStatus
  context_kind: ArchiveContextKind
  inventory_ready: boolean
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
  archive_mode: ArchiveMode
  source_entries: ArchiveSourceEntry[]
  total_input_bytes: number
  volume_size_bytes: number | null
  volume_tier_gb: number | null
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
  /** WinRAR 实际输出文件大小。标准分卷不得超过档位上限。 */
  size_bytes: number
  md5: string
  /** 案件选定的业务摘要；旧版 manifest 省略两个字段并使用 md5。 */
  hash_algorithm?: HashAlgorithm
  hash_value?: string
  disc_number: string
  disc_date: string
  /** 标准分卷的最小二进制容量档位；超大单卷不含此值。 */
  disc_capacity_bytes?: number
  /** 从 ArchiveManifest 继承的 WinRAR 档位分卷上限（兼容）。 */
  volume_size_bytes: number | null
  continuity_check: 'passed'
}

export interface ArchiveManifest {
  manifest_id: string
  plan_id: string
  archive_base_name: string
  archive_mode: ArchiveMode
  /** 以字节表示的 WinRAR 档位分卷上限（所有分卷值相同）。 */
  volume_size_bytes: number | null
  volume_tier_gb: number | null
  max_part_count: number
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
  manifest: ArchiveManifest | null
  plan: ArchivePlan | null
  diagnostics: ArchiveDiagnostic[]
  attachment_preview?: {
    columns: { key: string; title: string; width?: string }[]
    rows: Record<string, string>[]
  } | null
}
