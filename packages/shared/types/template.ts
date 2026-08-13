export type TemplateId = string

export type TemplateApprovalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'revoked'

export type TemplateErrorCode =
  | 'TEMPLATE_UNKNOWN'
  | 'TEMPLATE_NOT_APPROVED'
  | 'TEMPLATE_ASSET_MISSING'
  | 'TEMPLATE_FINGERPRINT_MISMATCH'
  | 'TEMPLATE_RULE_VALIDATION_FAILED'

export type WordArtifactValidity =
  | 'valid'
  | 'invalidated_by_template_change'

export interface TemplateVersionRef {
  template_id: TemplateId
  version: string
}

export interface TemplateApprovalRecord {
  approval_record_id: string
  status: TemplateApprovalStatus
  acceptance_summary: string
  recorded_at: string
}

export interface TemplateValidationRuleRef {
  rule_id: string
  version: string
}

export interface TemplateVersion {
  schema_version: 1
  template_ref: TemplateVersionRef
  display_name: string
  fingerprint: string
  validation_rules: TemplateValidationRuleRef[]
  approval_record: TemplateApprovalRecord
  asset_id: string
  registered_at: string
}

export interface TemplateManagementRecord extends TemplateVersion {
  is_default: boolean
  can_delete: boolean
  can_customize: boolean
  customization: TemplateCustomization
}

export interface TemplateManagementResponse {
  templates: TemplateManagementRecord[]
  default_template_ref: TemplateVersionRef | null
  defaults_revision: number
}

export type TemplateBodyFont = '仿宋_GB2312' | '仿宋' | '宋体'
export type TemplateBodyFontSize = 14 | 15 | 16 | 17 | 18

export interface TemplateCustomization {
  document_title: string
  body_font: TemplateBodyFont
  body_font_size: TemplateBodyFontSize
}

export interface DeriveTemplateRequest {
  source_template_ref: TemplateVersionRef
  template_ref: TemplateVersionRef
  display_name: string
  customization: TemplateCustomization
}

export interface TemplateValidationSuccess {
  valid: true
  template: TemplateVersion
  validated_at: string
}

export interface TemplateValidationFailure {
  valid: false
  error_code: TemplateErrorCode
  safe_summary: string
}

export type TemplateValidationResult =
  | TemplateValidationSuccess
  | TemplateValidationFailure

export interface TemplateSelectionImpact {
  word_artifact_validity: 'invalidated_by_template_change'
  archive_plan_changed: false
  archive_task_created: false
  manifest_changed: false
  disc_mapping_changed: false
}
