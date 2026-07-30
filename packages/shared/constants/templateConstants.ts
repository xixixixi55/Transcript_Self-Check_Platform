import type {
  TemplateApprovalStatus,
  TemplateErrorCode,
  WordArtifactValidity,
} from '../types'

export const TEMPLATE_APPROVAL_STATUS = {
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  REVOKED: 'revoked',
} as const satisfies Readonly<Record<string, TemplateApprovalStatus>>

export const TEMPLATE_ERROR_CODES = {
  UNKNOWN: 'TEMPLATE_UNKNOWN',
  NOT_APPROVED: 'TEMPLATE_NOT_APPROVED',
  ASSET_MISSING: 'TEMPLATE_ASSET_MISSING',
  FINGERPRINT_MISMATCH: 'TEMPLATE_FINGERPRINT_MISMATCH',
  RULE_VALIDATION_FAILED: 'TEMPLATE_RULE_VALIDATION_FAILED',
} as const satisfies Readonly<Record<string, TemplateErrorCode>>

export const TEMPLATE_CHANGE_WORD_ARTIFACT_VALIDITY =
  'invalidated_by_template_change' as const satisfies WordArtifactValidity
