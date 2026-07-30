// Layer 0: SharedTypes — 前后端共享的类型定义（实体、DTO、API 契约）

import type { InspectorSnapshot, MaterialClassificationStatus, MaterialPhotoGroup, PrimarySoftware } from './canonical'

/** 文书类型枚举 */
export enum RecordType {
  ELECTRONIC_INSPECTION = 'electronic_inspection',
  FORENSIC_REPORT = 'forensic_report',
  DIGITAL_FORENSIC = 'digital_forensic',
  SCENE_TRIPLE_RECORD = 'scene_triple_record',
  SCENE_INSPECTION = 'scene_inspection',
  FORENSIC_MEDICAL = 'forensic_medical',
}

/** 文书状态 */
export enum RecordStatus {
  DRAFT = 'draft',
  COMPLETED = 'completed',
  ARCHIVED = 'archived',
}

// ─── 检查笔录全文结构 ───

/** 检材条目 */
export interface EvidenceItem {
  id: string
  /**
   * Case-scoped stable evidence identity. Legacy DTOs may omit this during
   * migration; it is assigned once when a persistent case snapshot is made.
   */
  evidence_id?: string
  device_type: string         // 报告明确的设备类型字段；具体型号单独放在 model
  device_name?: string        // 品牌 + 有效型号组成的统一设备展示名称
  brand?: string              // 报告中对应检材的真实品牌
  device_type_source?: 'report_field' | 'legacy_display'
  model?: string              // 具体型号
  imei1?: string
  imei2?: string
  serial_number?: string
  evidence_number: string     // 检材编号，如 SYN-JC00000001
  material_type?: 'phone' | 'tablet' | 'unconfirmed'
  material_type_status?: MaterialClassificationStatus
  material_type_source?: 'report' | 'user' | 'none'
  material_type_diagnostic?: string
}

/** 检查人员 */
export interface Inspector {
  name: string
  unit: string
  badge_number: string
}

/** 检查人员库记录，仅代表当前可管理/选择的人员。 */
export interface InspectorLibraryRecord {
  id: string
  name: string
  unit: string
  police_number: string
  enabled: boolean
  created_at: string
  updated_at: string
}

/** 软件工具 */
export interface SoftwareItem {
  name: string
  version: string
}

/** 检查过程步骤 */
export interface ProcessStep {
  step_number: number
  content: string
}

/** 检查结果 */
export interface InspectionResult {
  evidence_number: string
  software_name: string
  software_version: string
  data_summary: string        // 检出数据分类摘要
  rar_filename: string
  md5_hash: string
  file_size: string
}

/** 表格数据 */
export interface TableData {
  columns: { key: string; title: string; width?: string }[]
  rows: Record<string, string>[]
}

/** 检查笔录全文 */
export interface InspectionReport {
  title: string                          // "电子数据检查笔录"
  document_number: string                // "xx电检〔2026〕xx号"
  case_number?: string                   // 案件编号（从报告解析），用于生成文号
  introduction: {
    entrust_unit: string                 // (一) 委托单位
    entrust_persons: string[]            // (二) 委托人（多人，顿号分隔展示）
    entrust_time: string                 // (三) 委托时间
    case_summary: string                 // (四) 案件简要情况
    evidence_list: EvidenceItem[]        // (五) 检材情况
    inspection_requirement: string       // (六) 检查要求
    inspection_time_range: string        // (七) 检查起止时间
    inspectors: Inspector[]              // (八) 检查人员 legacy 投影
    inspector_snapshots?: InspectorSnapshot[]
    inspection_place: string             // (九) 检查地点
  }
  inspection: {
    method: string                       // (一) 检查方法
    hardware_device: string              // 硬件设备名称
    primary_software?: PrimarySoftware   // 主取证软件唯一权威编辑结构
    software_tools: SoftwareItem[]       // (二) 检查设备 — 软件
    process_steps: ProcessStep[]         // (三) 检查过程
    result: InspectionResult             // (四) 检查结果
  }
  attachments: {
    extract_list: TableData              // 附件1: 电子数据提取固定清单
    photo_ids: string[]                  // 附件2: 已上传检材照片 ID 列表
    photo_groups?: MaterialPhotoGroup[]  // 附件2: 显式检材-照片归属和组内顺序
    disc_number: string                  // 附件3: 光盘编号
    burning_date?: string                // 附件3: 刻录时间（民警填写）
    disc_sequence?: import('./discSequence').DiscSequence
  }
}

// ─── API 请求/响应 ───

/** RAR/压缩包文件信息 */
export interface RarInfo {
  filename: string
  md5: string
  size_bytes: number
  size_display: string
}

/** 解析报告响应 */
export interface ParseReportResponse {
  report: InspectionReport
  parsed_files: string[]
  rar_info: RarInfo | null
  archive_context_id?: string | null
  archive_context?: import('./archive').ArchiveContextSummary | null
  archive_context_kind?: import('./archive').ArchiveContextKind
  archive_preparation_status?: import('./archive').ArchivePreparationStatus
  archive_status?: import('./archive').ArchiveExecutionStatus | import('./archive').ArchivePreparationStatus
}

/** 一键清空报告解析缓存的结果。 */
export interface ClearReportParsingCacheResponse {
  cleared_count: number
}

/** 导出笔录请求 */
export interface ExportRecordRequest {
  report: InspectionReport
  photo_ids: string[]
}

/** 导出笔录响应 */
export interface ExportRecordResponse {
  download_url: string
  filename: string
  document_number: string
}

// ─── 硬件设备管理 ───

/** 硬件设备 */
export interface HardwareDevice {
  id: string
  name: string
  model: string
  description?: string
  created_at?: string
}

// ─── 原有类型（保留兼容） ───

export interface InspectionRecord {
  id: string
  record_type: RecordType
  case_number: string
  created_at: string
  updated_at: string
  source_report_path: string
  template_path: string
  output_path: string
  status: RecordStatus
}

export interface ParsedReport {
  id: string
  source_path: string
  parsed_at: string
  extracted_fields: Record<string, string>
  raw_sections: Record<string, string>
}

export interface RecordTemplate {
  id: string
  name: string
  record_type: RecordType
  file_path: string
  placeholders: string[]
  version: string
}

export interface GenerateRecordRequest {
  report_path: string
  template_id: string
  record_type: RecordType
  case_number: string
}

export interface UpdateRecordRequest {
  fields: Record<string, string>
}

export interface RecordListResponse {
  records: InspectionRecord[]
  total: number
}

export * from './canonical'
export * from './archive'
export * from './discSequence'
export * from './exportGate'
export * from './pipeline'
export * from './shadow'
export * from './workbench'
export * from './archiveAttempt'
export * from './demoReadiness'
export * from './wordDownload'
export * from './task'
export * from './archiveTask'
