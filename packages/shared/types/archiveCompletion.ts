// 第 0 层：SharedTypes — 延迟光盘映射与统一导出契约。

import type { CaseLifecycle } from './workbench'
import type { ArchiveMedium } from './archive'

/** 根据首个光盘编号序列生成的单个 RAR 分卷光盘映射。 */
export interface ArchivePartDiscMapping {
  part_number: number
  disc_number: string
  disc_date: string
}

export interface DiscMappingRequest {
  /** 案件版本保护值，与工作台命令语义一致。 */
  expected_revision: number
  /** 显示分卷映射时观测到的归档计划行版本。 */
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
  /** 原生目录选择器返回的路径；后端会再次验证。 */
  export_path: string
  /** 选择器签发的一次性授权；后端只写入此路径。 */
  directory_token: string
  /** 用户选择的 Word 文件名（不含目录）；覆盖自动生成的名称。 */
  word_filename: string
}

export interface UnifiedExportOutput {
  export_path: string
  word_filename: string
  rar_filenames: string[]
  exported_at: string
}

export interface UnifiedExportResult {
  case_id: string
  task_id: string
  expected_revision: number
  lifecycle: CaseLifecycle
  output: UnifiedExportOutput
}

export interface OpenExportDirectoryResult {
  case_id: string
  opened: true
  exported_at: string
}

/**
 * 后端打开的可信原生目录选择器的结果。
 * 导出路径始终由选择器选定，绝不由用户键入。
 * 一次性授权由 export-bundle 消耗，确保后端只写入选择器授权的路径。
 */
export type ExportDirectoryResult =
  | { path: string; token: string }
  | { cancelled: true }

/** 投影到工作台卡片和审计中的持久导出日志行。 */
export interface ExportRecord {
  export_id: string
  case_id: string
  task_id: string
  export_path: string
  word_filename: string
  rar_filenames: string[]
  /** @deprecated 兼容统一导出曾发布 PNG 时创建的记录。 */
  hash_verification_image?: string
  /** @deprecated 兼容 PNG 导出前创建的持久记录。 */
  hash_verification_html?: string
  exported_at: string
}

/**
 * 投影到案件卡片的归档完成状态。由生命周期加持久化的光盘映射完成标志推导；
 * 并非独立的生命周期值。
 */
export type ArchiveCompletionStatus =
  | 'compressing'
  | 'disc_pending'
  | 'archive_complete'
  | 'exported'
