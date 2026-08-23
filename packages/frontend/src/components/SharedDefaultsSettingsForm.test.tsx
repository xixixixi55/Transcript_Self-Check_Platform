import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import { SharedDefaultsSettingsForm } from './SharedDefaultsSettingsForm'

vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const putMock = vi.mocked(axios.put)
const defaults = {
  schema_version: 1, deployment_instance_id: 'SYNTHETIC-DEPLOYMENT', revision: 2,
  entrust_unit_prefix: 'SYNTHETIC-PREFIX', document_number: 'SYNTHETIC-DOC',
  inspection_place: 'SYNTHETIC-PLACE', inspection_method: 'SYNTHETIC-METHOD',
  hardware_device: 'SYNTHETIC-DEVICE',
  inspector_order: ['SYNTHETIC-NAME|SYNTHETIC-UNIT|SYNTHETIC-POSITION|SYNTHETIC-001'],
  disc_number_prefix: 'GP', hash_algorithm: 'md5', migration_decision: 'ignored', updated_at: '2026-08-23T00:00:00Z',
}

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: () => ({
      matches: false, media: '', onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }),
  })
})

beforeEach(() => {
  vi.clearAllMocks()
  getMock.mockResolvedValue({ data: { data: defaults } })
  putMock.mockResolvedValue({ data: { data: { ...defaults, revision: 3, document_number: '' } } })
})

describe('SharedDefaultsSettingsForm', () => {
  it('shows all settings and saves an intentional clear without default inspectors', async () => {
    render(<SharedDefaultsSettingsForm />)

    expect(await screen.findByDisplayValue('SYNTHETIC-DOC')).toBeTruthy()
    expect(screen.getByDisplayValue('SYNTHETIC-NAME')).toBeTruthy()
    fireEvent.click(screen.getByRole('radio', { name: 'SHA-256' }))

    fireEvent.change(screen.getByLabelText('文号'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: '删除第1名检查人员' }))
    fireEvent.click(screen.getByRole('button', { name: /保存默认设置/ }))

    await waitFor(() => expect(putMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_DEFAULTS,
      expect.objectContaining({
        expected_revision: 2,
        values: expect.objectContaining({
          document_number: '', inspector_order: [], hash_algorithm: 'sha256',
        }),
      }),
    ))
    expect(await screen.findByText('笔录默认设置已保存')).toBeTruthy()
  })

  it('keeps server values visible and offers reload after a revision conflict', async () => {
    putMock.mockRejectedValue({ response: { data: { detail: { code: 'REVISION_CONFLICT' } } } })
    render(<SharedDefaultsSettingsForm />)
    await screen.findByDisplayValue('SYNTHETIC-DOC')

    fireEvent.change(screen.getByLabelText('检查地点'), { target: { value: 'SYNTHETIC-NEW-PLACE' } })
    fireEvent.click(screen.getByRole('button', { name: /保存默认设置/ }))

    expect(await screen.findByText('设置已被其他窗口更新')).toBeTruthy()
    const reloadButtons = screen.getAllByRole('button', { name: /重新加载/ })
    expect(reloadButtons.length).toBeGreaterThan(0)

    fireEvent.click(reloadButtons[0])
    expect((await screen.findAllByText('放弃未保存的修改？')).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: '继续编辑' }))
    expect(getMock).toHaveBeenCalledTimes(1)
  })
})
