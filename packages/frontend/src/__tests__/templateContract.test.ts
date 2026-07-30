import { describe, expect, it } from 'vitest'
import {
  TEMPLATE_APPROVAL_STATUS,
  TEMPLATE_CHANGE_WORD_ARTIFACT_VALIDITY,
  TEMPLATE_ERROR_CODES,
} from '@biji/shared/constants'
import type {
  TemplateSelectionImpact,
  TemplateValidationResult,
  TemplateVersion,
  TemplateVersionRef,
} from '@biji/shared/types'

const approvedTemplate: TemplateVersion = {
  schema_version: 1,
  template_ref: {
    template_id: 'template-SYNTHETIC-electronic-inspection',
    version: '1.0.0',
  },
  display_name: 'SYNTHETIC 已审核电子数据检查笔录模板',
  fingerprint: 'sha256:SYNTHETIC_TEMPLATE_FINGERPRINT',
  validation_rules: [
    { rule_id: 'rule-SYNTHETIC-vml-pagination', version: '1.0.0' },
  ],
  approval_record: {
    approval_record_id: 'approval-SYNTHETIC-001',
    status: TEMPLATE_APPROVAL_STATUS.APPROVED,
    acceptance_summary: 'SYNTHETIC acceptance fixture',
    recorded_at: '2026-07-30T00:00:00.000Z',
  },
  asset_id: 'asset-SYNTHETIC-template-001',
  registered_at: '2026-07-30T00:00:00.000Z',
}

describe('Phase 4 approved template contract', () => {
  it('binds an approved semantic version to its asset fingerprint and rules', () => {
    const result: TemplateValidationResult = {
      valid: true,
      template: approvedTemplate,
      validated_at: '2026-07-30T00:01:00.000Z',
    }

    expect(result.valid).toBe(true)
    if (result.valid) {
      expect(result.template.template_ref.version).toBe('1.0.0')
      expect(result.template.fingerprint).toBe('sha256:SYNTHETIC_TEMPLATE_FINGERPRINT')
      expect(result.template.validation_rules).toEqual([
        { rule_id: 'rule-SYNTHETIC-vml-pagination', version: '1.0.0' },
      ])
      expect(result.template.approval_record.status).toBe('approved')
    }
  })

  it.each([
    ['unknown template', TEMPLATE_ERROR_CODES.UNKNOWN, 'TEMPLATE_UNKNOWN'],
    ['unapproved template', TEMPLATE_ERROR_CODES.NOT_APPROVED, 'TEMPLATE_NOT_APPROVED'],
  ])('represents a stable rejection for %s', (_case, errorCode, expectedCode) => {
    const result: TemplateValidationResult = {
      valid: false,
      error_code: errorCode,
      safe_summary: 'SYNTHETIC template selection rejected',
    }

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error_code).toBe(expectedCode)
      expect(result.safe_summary).toBe('SYNTHETIC template selection rejected')
    }
  })

  it('round-trips only the template ID and version in a case reference', () => {
    const reference: TemplateVersionRef = approvedTemplate.template_ref
    const restored = JSON.parse(JSON.stringify(reference)) as TemplateVersionRef

    expect(restored).toEqual({
      template_id: 'template-SYNTHETIC-electronic-inspection',
      version: '1.0.0',
    })
    expect(Object.keys(restored).sort()).toEqual(['template_id', 'version'])
  })

  it('invalidates Word without changing archive, Manifest, or disc mapping facts', () => {
    const impact: TemplateSelectionImpact = {
      word_artifact_validity: TEMPLATE_CHANGE_WORD_ARTIFACT_VALIDITY,
      archive_plan_changed: false,
      archive_task_created: false,
      manifest_changed: false,
      disc_mapping_changed: false,
    }

    expect(impact).toEqual({
      word_artifact_validity: 'invalidated_by_template_change',
      archive_plan_changed: false,
      archive_task_created: false,
      manifest_changed: false,
      disc_mapping_changed: false,
    })
  })
})
