import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { TemplateManagementRecord } from '@biji/shared/types'
import { useTemplateManagement } from '../hooks/useTemplateManagement'
import TemplateManager from './TemplateManager'

vi.mock('../hooks/useTemplateManagement', () => ({ useTemplateManagement: vi.fn() }))

const useTemplateManagementMock = vi.mocked(useTemplateManagement)

const defaultTemplate: TemplateManagementRecord = {
  schema_version: 1,
  template_ref: { template_id: 'template-SYNTHETIC-default', version: '1.0.0' },
  display_name: 'SYNTHETIC 默认模版', fingerprint: 'A'.repeat(64),
  validation_rules: [{ rule_id: 'current-template-profile', version: '1.0.0' }],
  approval_record: {
    approval_record_id: 'approval-SYNTHETIC-default', status: 'approved',
    acceptance_summary: 'SYNTHETIC', recorded_at: '2026-08-01T00:00:00Z',
  },
  asset_id: 'asset-SYNTHETIC-default', registered_at: '2026-08-01T00:00:00Z',
  is_default: true, can_delete: false,
}

const extraTemplate: TemplateManagementRecord = {
  ...defaultTemplate,
  template_ref: { template_id: 'template-SYNTHETIC-extra', version: '2.0.0' },
  display_name: 'SYNTHETIC 可删除模版', is_default: false, can_delete: true,
}

const setDefault = vi.fn(async () => true)
const addTemplate = vi.fn(async () => true)
const deleteTemplate = vi.fn(async () => true)

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
  vi.clearAllMocks()
  useTemplateManagementMock.mockReturnValue({
    templates: [defaultTemplate, extraTemplate], defaultTemplateRef: defaultTemplate.template_ref,
    defaultsRevision: 1, loading: false, saving: false, errorCode: null,
    reload: vi.fn(async () => undefined), setDefault, addTemplate, deleteTemplate,
  })
})

describe('TemplateManager', () => {
  it('shows default state and exposes add, default, and delete actions', async () => {
    render(<TemplateManager />)
    expect(screen.getByText('SYNTHETIC 默认模版')).toBeTruthy()
    expect(screen.getByText('默认模版')).toBeTruthy()

    fireEvent.click(screen.getAllByRole('button', { name: '设为默认' })[1])
    expect(setDefault).toHaveBeenCalledWith(extraTemplate.template_ref)
    fireEvent.click(screen.getAllByRole('button', { name: /删除/ })[1])
    fireEvent.click(screen.getByRole('button', { name: '确认撤销' }))
    expect(deleteTemplate).toHaveBeenCalledWith(extraTemplate.template_ref)

    fireEvent.click(screen.getByRole('button', { name: /添加模版/ }))
    fireEvent.change(screen.getByLabelText('模版 ID'), { target: { value: 'template-SYNTHETIC-new' } })
    fireEvent.change(screen.getByLabelText('版本'), { target: { value: '1.0.0' } })
    fireEvent.change(screen.getByLabelText('显示名称'), { target: { value: 'SYNTHETIC 新模版' } })
    const file = new File(['SYNTHETIC'], 'SYNTHETIC-new.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    const fileInput = document.querySelector('input[type="file"]')
    expect(fileInput).toBeTruthy()
    fireEvent.change(fileInput as HTMLInputElement, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText('SYNTHETIC-new.docx')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: '保存模版' }))
    await waitFor(() => expect(addTemplate).toHaveBeenCalledWith({
      templateId: 'template-SYNTHETIC-new', version: '1.0.0', displayName: 'SYNTHETIC 新模版', file,
    }))
  })
})
