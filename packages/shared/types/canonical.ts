/** 报告迁移边界共享的规范领域类型。 */

import type { DiscSequence } from './discSequence'

export type MaterialKind = 'phone' | 'tablet' | 'unconfirmed'
export type MaterialClassificationStatus = 'confirmed_by_report' | 'confirmed_by_user' | 'unconfirmed'
export type MaterialClassificationSource = 'report' | 'user' | 'none'

export type IdentifierType = 'imei1' | 'imei2' | 'serial_number'

export type SoftwareCategory =
  | 'main_forensic'
  | 'winrar'
  | 'python_hashlib'
  | 'hashmyfiles'
  | 'unclassified'

export type ConfirmationStatus = 'confirmed_by_report' | 'confirmed_by_user' | 'unconfirmed' | 'confirmed'

export interface FieldProvenance {
  source_type: string
  source_file?: string | null
  json_path?: string | null
  adapter: string
  confidence?: number | null
}

export interface MaterialIdentifier {
  type: IdentifierType
  value: string
  provenance: FieldProvenance[]
}

export interface MaterialClassification {
  status: MaterialClassificationStatus
  source: MaterialClassificationSource
  rule_id?: string
  diagnostic_code?: string
}

export interface Material {
  id: string
  evidence_number: string
  type: MaterialKind
  name: string
  model: string
  extractable?: boolean
  unextractable_reason?: string
  identifiers: MaterialIdentifier[]
  provenance: FieldProvenance[]
  classification: MaterialClassification
}

export interface InspectorSnapshot {
  /** 案件范围的稳定快照标识；旧版投影可能省略。 */
  snapshot_id?: string
  inspector_id?: string | null
  name: string
  unit: string
  position?: string
  police_number: string
  selected_order?: number
  captured_at?: string
  source_version?: string
}

export interface SoftwareTool {
  category: SoftwareCategory
  name: string
  version: string
  display_name: string
  provenance: FieldProvenance[]
  confirmation_status: ConfirmationStatus
}

export interface PrimarySoftwareCandidate {
  name: string
  version: string
}

export interface PrimarySoftware {
  name: string
  version: string
  display_name: string
  confirmation_status: ConfirmationStatus
  provenance: FieldProvenance[]
  candidates: PrimarySoftwareCandidate[]
}

export interface CanonicalCaseInfo {
  title: string
  document_number: string
  case_number: string
  case_name: string
  introduction: {
    entrust_unit: string
    entrust_persons: string[]
    entrust_time: string
    case_summary: string
    inspection_requirement: string
    inspection_place: string
  }
}

export interface CanonicalInspectionPeriod {
  created_at: string
  reported_at: string
  time_range: string
}

export interface CanonicalInspectionResult {
  evidence_number: string
  data_summary: string
  rar_filename: string
  md5_hash: string
  file_size: string
}

export interface CanonicalInspectionDetails {
  method: string
  hardware_device: string
  process_steps: { step_number: number; content: string }[]
  result: CanonicalInspectionResult
}

export interface PhotoReference {
  id: string
  provenance: FieldProvenance[]
}

export interface ArchiveManifestSummary {
  manifest_id: string
  status: 'pending' | 'validated' | 'unavailable'
}

/** 附件2：一个检材的正反两张有序照片。 */
export interface MaterialPhotoGroup {
  material_id: string
  material_number: string
  display_text: string
  ordered_image_ids: [string, string]
  source_order: number
}

export interface CanonicalAttachmentInputs {
  extract_list: { columns: { key: string; title: string; width?: string }[]; rows: Record<string, string>[] }
  photo_ids: string[]
  photo_groups?: MaterialPhotoGroup[]
  disc_number: string
  burning_date?: string | null
  disc_sequence?: DiscSequence
}

export interface CanonicalInspectionCase {
  case_info: CanonicalCaseInfo
  inspection_period: CanonicalInspectionPeriod
  materials: Material[]
  inspectors: InspectorSnapshot[]
  primary_software?: PrimarySoftware
  software_tools: SoftwareTool[]
  photos: PhotoReference[]
  archive_manifest?: ArchiveManifestSummary | null
  provenance: FieldProvenance[]
  inspection: CanonicalInspectionDetails
  attachments: CanonicalAttachmentInputs
}
