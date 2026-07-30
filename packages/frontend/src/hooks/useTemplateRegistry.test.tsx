import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS, TEMPLATE_APPROVAL_STATUS } from '@biji/shared/constants'
import type {
  CaseDraft,
  TemplateApprovalStatus,
  TemplateVersion,
  TemplateVersionRef,
} from '@biji/shared/types'
import { isApprovedTemplateVersion, useTemplateRegistry } from './useTemplateRegistry'

vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const putMock = vi.mocked(axios.put)

function template(
  version: string,
  status: TemplateApprovalStatus = TEMPLATE_APPROVAL_STATUS.APPROVED,
): TemplateVersion {
  return {
    schema_version: 1,
    template_ref: { template_id: 'template-SYNTHETIC-record', version },
    display_name: `SYNTHETIC 模板 ${version}`,
    fingerprint: `sha256:SYNTHETIC-${version}`,
    validation_rules: [{ rule_id: 'rule-SYNTHETIC-layout', version: '1.0.0' }],
    approval_record: {
      approval_record_id: `approval-SYNTHETIC-${version}`,
      status,
      acceptance_summary: `SYNTHETIC acceptance ${version}`,
      recorded_at: '2026-07-30T00:00:00.000Z',
    },
    asset_id: `asset-SYNTHETIC-${version}`,
    registered_at: '2026-07-30T00:00:00.000Z',
  }
}

function savedDraft(templateRef: TemplateVersionRef): CaseDraft {
  return {
    schema_version: 1,
    case_id: 'case-SYNTHETIC-template',
    case_name: 'SYNTHETIC template case',
    case_summary: 'TEST template selection',
    report: {} as CaseDraft['report'],
    report_version: 'legacy-v1',
    field_states: {},
    asset_refs: [],
    template_ref: templateRef,
    archive_plan_id: 'plan-SYNTHETIC-stable',
    lifecycle: 'review_ready',
    revision: 8,
    created_at: '2026-07-30T00:00:00.000Z',
    updated_at: '2026-07-30T00:01:00.000Z',
  }
}

const safeImpact = {
  word_artifact_validity: 'invalidated_by_template_change',
  archive_plan_changed: false,
  archive_task_created: false,
  manifest_changed: false,
  disc_mapping_changed: false,
} as const

describe('useTemplateRegistry', () => {
  beforeEach(() => vi.clearAllMocks())

  it('keeps only complete approved versions from the registry response', async () => {
    const approved = template('1.0.0')
    const pending = template('2.0.0', TEMPLATE_APPROVAL_STATUS.PENDING)
    const malformed = { ...template('3.0.0'), fingerprint: '' }
    getMock.mockResolvedValue({ data: { data: [approved, pending, malformed] } })

    const { result } = renderHook(() => useTemplateRegistry({
      caseId: 'case-SYNTHETIC-template',
      currentTemplateRef: null,
      expectedRevision: 7,
      enabled: true,
      editingEnabled: true,
    }))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(getMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_TEMPLATES)
    expect(result.current.templates).toEqual([approved])
    expect(isApprovedTemplateVersion(pending)).toBe(false)
    expect(isApprovedTemplateVersion(malformed)).toBe(false)
  })

  it('saves only the approved ID/version reference and accepts a safe impact', async () => {
    const approved = template('1.1.0')
    const onSelected = vi.fn()
    getMock.mockResolvedValue({ data: { data: [approved] } })
    putMock.mockResolvedValue({
      data: { data: { draft: savedDraft(approved.template_ref), impact: safeImpact } },
    })
    const { result } = renderHook(() => useTemplateRegistry({
      caseId: 'case-SYNTHETIC-template',
      currentTemplateRef: { template_id: approved.template_ref.template_id, version: '1.0.0' },
      expectedRevision: 7,
      enabled: true,
      editingEnabled: true,
      leaseId: 'lease-SYNTHETIC',
      leaseToken: 'token-SYNTHETIC',
      onSelected,
    }))
    await waitFor(() => expect(result.current.templates).toHaveLength(1))

    await act(async () => {
      expect(await result.current.selectTemplate(approved.template_ref)).toBe(true)
    })

    expect(putMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_CASE_TEMPLATE('case-SYNTHETIC-template'),
      {
        template_ref: approved.template_ref,
        expected_revision: 7,
        lease_id: 'lease-SYNTHETIC',
        lease_token: 'token-SYNTHETIC',
      },
    )
    expect(putMock.mock.calls[0][1]).not.toHaveProperty('fingerprint')
    expect(putMock.mock.calls[0][1]).not.toHaveProperty('asset_id')
    expect(result.current.impact).toEqual(safeImpact)
    expect(onSelected).toHaveBeenCalledWith(expect.objectContaining({
      template_ref: approved.template_ref,
      archive_plan_id: 'plan-SYNTHETIC-stable',
    }))
  })

  it('rejects unapproved selections and unsafe archive impact responses', async () => {
    const approved = template('1.0.0')
    const pending = template('2.0.0', TEMPLATE_APPROVAL_STATUS.PENDING)
    getMock.mockResolvedValue({ data: { data: [approved, pending] } })
    const { result } = renderHook(() => useTemplateRegistry({
      caseId: 'case-SYNTHETIC-template',
      currentTemplateRef: null,
      expectedRevision: 7,
      enabled: true,
      editingEnabled: true,
    }))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      expect(await result.current.selectTemplate(pending.template_ref)).toBe(false)
    })
    expect(result.current.errorCode).toBe('TEMPLATE_NOT_APPROVED')
    expect(putMock).not.toHaveBeenCalled()

    putMock.mockResolvedValue({
      data: {
        data: {
          draft: savedDraft(approved.template_ref),
          impact: { ...safeImpact, manifest_changed: true },
        },
      },
    })
    await act(async () => {
      expect(await result.current.selectTemplate(approved.template_ref)).toBe(false)
    })
    expect(result.current.errorCode).toBe('TEMPLATE_SELECTION_IMPACT_INVALID')
  })
})
