// Layer 0: SharedTypes — deferred disc mapping and unified export contracts.

import type { CaseLifecycle } from './workbench'

/** One RAR part's disc mapping produced from the first disc number sequence. */
export interface ArchivePartDiscMapping {
  part_number: number
  disc_number: string
  disc_date: string
}

export interface DiscMappingRequest {
  /** Case revision guard, mirrors workbench command semantics. */
  expected_revision: number
  first_disc_number: string
}

export interface DiscMappingResult {
  case_id: string
  task_id: string
  expected_revision: number
  lifecycle: CaseLifecycle
  prefix: string
  disc_date: string
  parts: ArchivePartDiscMapping[]
}

export interface UnifiedExportRequest {
  expected_revision: number
  /** Path returned by the native directory picker; the backend re-validates it. */
  export_path: string
}

export interface UnifiedExportOutput {
  export_path: string
  word_filename: string
  rar_filenames: string[]
  hash_verification_html: string
  exported_at: string
}

export interface UnifiedExportResult {
  case_id: string
  task_id: string
  expected_revision: number
  lifecycle: CaseLifecycle
  output: UnifiedExportOutput
}

/** Durable export log row projected for the workbench card and audit. */
export interface ExportRecord {
  export_id: string
  case_id: string
  task_id: string
  export_path: string
  word_filename: string
  rar_filenames: string[]
  hash_verification_html: string
  exported_at: string
}

/**
 * Archive completion state projected for the case card. Derived from lifecycle
 * plus a persisted disc-mapping-complete flag; not a separate lifecycle value.
 */
export type ArchiveCompletionStatus =
  | 'compressing'
  | 'disc_pending'
  | 'archive_complete'
  | 'exported'
