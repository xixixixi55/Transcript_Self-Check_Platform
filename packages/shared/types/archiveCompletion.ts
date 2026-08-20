// Layer 0: SharedTypes — deferred disc mapping and unified export contracts.

import type { CaseLifecycle } from './workbench'
import type { ArchiveMedium } from './archive'

/** One RAR part's disc mapping produced from the first disc number sequence. */
export interface ArchivePartDiscMapping {
  part_number: number
  disc_number: string
  disc_date: string
}

export interface DiscMappingRequest {
  /** Case revision guard, mirrors workbench command semantics. */
  expected_revision: number
  /** Archive-plan row revision observed with the displayed part mappings. */
  expected_plan_row_revision: number
  first_disc_number: string
}

export interface DiscMappingResult {
  case_id: string
  task_id: string
  expected_revision: number
  plan_row_revision: number
  lifecycle: CaseLifecycle
  archive_medium: ArchiveMedium
  prefix: string
  disc_date: string
  parts: ArchivePartDiscMapping[]
}

export interface UnifiedExportRequest {
  expected_revision: number
  /** Path returned by the native directory picker; the backend re-validates it. */
  export_path: string
  /** One-use grant issued by the picker; the backend only writes to this path. */
  directory_token: string
  /** User-chosen Word file name (without directory); overrides the auto-generated one. */
  word_filename: string
}

export interface UnifiedExportOutput {
  export_path: string
  word_filename: string
  rar_filenames: string[]
  hash_verification_image: string
  exported_at: string
}

export interface UnifiedExportResult {
  case_id: string
  task_id: string
  expected_revision: number
  lifecycle: CaseLifecycle
  output: UnifiedExportOutput
}

/**
 * Result of the trusted native directory picker opened by the backend.
 * The export path is always chosen by the picker, never typed by the user.
 * The one-use grant is consumed by export-bundle so the backend only ever
 * writes to a picker-authorised path.
 */
export type ExportDirectoryResult =
  | { path: string; token: string }
  | { cancelled: true }

/** Durable export log row projected for the workbench card and audit. */
export interface ExportRecord {
  export_id: string
  case_id: string
  task_id: string
  export_path: string
  word_filename: string
  rar_filenames: string[]
  /** HashMyFiles-style verification screenshot published by current exports. */
  hash_verification_image?: string
  /** @deprecated Compatibility field for durable records created before PNG export. */
  hash_verification_html?: string
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
