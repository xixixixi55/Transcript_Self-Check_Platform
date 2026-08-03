import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { TemplateManagementRecord, TemplateManagementResponse } from '@biji/shared/types'
import { useTemplateManagement } from './useTemplateManagement'

vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const putMock = vi.mocked(axios.put)
const postMock = vi.mocked(axios.post)
const deleteMock = vi.mocked(axios.delete)

const current: TemplateManagementRecord = {
  schema_version: 1,
  template_ref: { template_id: 'template-SYNTHETIC-current', version: '1.0.0' },
  display_name: 'SYNTHETIC 当前模版',
  fingerprint: 'A'.repeat(64),
  validation_rules: [{ rule_id: 'current-template-profile', version: '1.0.0' }],
  approval_record: {
    approval_record_id: 'approval-SYNTHETIC-current', status: 'approved',
    acceptance_summary: 'SYNTHETIC 已校验', recorded_at: '2026-08-01T00:00:00Z',
  },
  asset_id: 'asset-SYNTHETIC-current', registered_at: '2026-08-01T00:00:00Z',
  is_default: true, can_delete: false,
}

const uploaded: TemplateManagementRecord = {
  ...current,
  template_ref: { template_id: 'template-SYNTHETIC-uploaded', version: '1.0.0' },
  display_name: 'SYNTHETIC 上传模版',
  is_default: false,
  can_delete: true,
}

function response(
  items: TemplateManagementRecord[] = [current],
  defaultTemplateRef = current.template_ref,
): { data: { data: TemplateManagementResponse } } {
  return {
    data: {
      data: {
        templates: items,
        default_template_ref: defaultTemplateRef,
        defaults_revision: 1,
      },
    },
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getMock.mockResolvedValue(response())
})

describe('useTemplateManagement', () => {
  it('loads managed templates and persists a new default', async () => {
    const changed = response(
      [{ ...current, is_default: false, can_delete: true }, { ...uploaded, is_default: true, can_delete: false }],
      uploaded.template_ref,
    )
    putMock.mockResolvedValue(changed)
    const view = renderHook(() => useTemplateManagement())
    await waitFor(() => expect(view.result.current.templates).toHaveLength(1))

    await act(async () => {
      await view.result.current.setDefault(uploaded.template_ref)
    })
    expect(putMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_TEMPLATE_DEFAULT, {
      template_ref: uploaded.template_ref, expected_defaults_revision: 1,
    })
    expect(view.result.current.templates[1].is_default).toBe(true)
  })

  it('uploads through FormData and revokes a removable version', async () => {
    postMock.mockResolvedValue({ data: { data: uploaded } })
    deleteMock.mockResolvedValue(response())
    const view = renderHook(() => useTemplateManagement())
    await waitFor(() => expect(view.result.current.templates).toHaveLength(1))
    const file = new File(['SYNTHETIC-DOCX'], 'SYNTHETIC-template.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })

    await act(async () => {
      await view.result.current.addTemplate({
        templateId: uploaded.template_ref.template_id,
        version: uploaded.template_ref.version,
        displayName: uploaded.display_name,
        file,
      })
    })
    const form = postMock.mock.calls[0][1] as FormData
    expect(form.get('template_id')).toBe(uploaded.template_ref.template_id)
    expect(form.get('file')).toBe(file)

    await act(async () => {
      await view.result.current.deleteTemplate(uploaded.template_ref)
    })
    expect(deleteMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_TEMPLATE(uploaded.template_ref.template_id, uploaded.template_ref.version),
    )
  })
})
