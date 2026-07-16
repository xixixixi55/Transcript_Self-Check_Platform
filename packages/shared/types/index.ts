// Layer 0: SharedTypes — 前后端共享的类型定义（实体、DTO、API 契约）

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
  device_type: string         // 设备类型，如"iPhone 13 Pro"
  model?: string              // 具体型号
  imei1?: string
  imei2?: string
  serial_number?: string
  evidence_number: string     // 检材编号，如 SYN-JC00000001
}

/** 检查人员 */
export interface Inspector {
  name: string
  unit: string
  badge_number: string
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
    inspectors: Inspector[]              // (八) 检查人员
    inspection_place: string             // (九) 检查地点
  }
  inspection: {
    method: string                       // (一) 检查方法
    hardware_device: string              // 硬件设备名称
    software_tools: SoftwareItem[]       // (二) 检查设备 — 软件
    process_steps: ProcessStep[]         // (三) 检查过程
    result: InspectionResult             // (四) 检查结果
  }
  attachments: {
    extract_list: TableData              // 附件1: 电子数据提取固定清单
    photo_ids: string[]                  // 附件2: 已上传检材照片 ID 列表
    disc_number: string                  // 附件3: 光盘编号
    burning_date?: string                // 附件3: 刻录时间（民警填写）
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
