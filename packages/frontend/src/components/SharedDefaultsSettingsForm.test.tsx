import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import { SharedDefaultsSettingsForm } from './SharedDefaultsSettingsForm'

vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn() } }))
vi.mock('./HardwareDeviceSelect', () => ({
  HardwareDeviceSelect: ({ options = [], value, onChange, loading: _loading,
    allowClear: _allowClear, ...props }: any) => (
    <select value={value || ''} onChange={event => onChange?.(event.target.value)} {...props}>
      <option value="" />
      {options.map((option: { label: string; value: string }) => (
        <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
  ),
}))

const getMock = vi.mocked(axios.get)
const putMock = vi.mocked(axios.put)
const devices = [
  { id: 'device-SYNTHETIC-1', name: 'SYNTHETIC-DEVICE', company: 'SYNTHETIC-COMPANY' },
  { id: 'device-SYNTHETIC-2', name: 'SYNTHETIC-DEVICE-2', company: 'SYNTHETIC-COMPANY' },
]
const inspectors = [
  {
    id: 'inspector-SYNTHETIC-1', name: 'SYNTHETIC-NAME', unit: 'SYNTHETIC-UNIT',
    position: 'SYNTHETIC-POSITION', police_number: 'SYNTHETIC-001',
    created_at: '2026-08-23T00:00:00Z', updated_at: '2026-08-23T00:00:00Z',
  },
  {
    id: 'inspector-SYNTHETIC-2', name: 'SYNTHETIC-NAME-2', unit: 'SYNTHETIC-UNIT-2',
    position: 'SYNTHETIC-POSITION-2', police_number: 'SYNTHETIC-002',
    created_at: '2026-08-23T00:00:00Z', updated_at: '2026-08-23T00:00:00Z',
  },
]
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
  getMock.mockImplementation(async url => {
    if (url === API_ENDPOINTS.DEVICES) return { data: { data: devices } }
    if (url === API_ENDPOINTS.INSPECTORS) return { data: { data: inspectors } }
    return { data: { data: defaults } }
  })
  putMock.mockResolvedValue({ data: { data: { ...defaults, revision: 3, document_number: '' } } })
})

describe('SharedDefaultsSettingsForm', () => {
  it('shows all settings and saves an intentional clear without default inspectors', async () => {
    render(<SharedDefaultsSettingsForm />)

    expect(await screen.findByDisplayValue('SYNTHETIC-DOC')).toBeTruthy()
    expect(screen.getByText('SYNTHETIC-NAME')).toBeTruthy()
    fireEvent.click(screen.getByRole('radio', { name: 'SHA-256' }))

    fireEvent.change(screen.getByLabelText('文号'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: '移除1' }))
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

  it('selects a managed device and reuses inspector cards for add and drag sorting', async () => {
    render(<SharedDefaultsSettingsForm />)
    await screen.findByDisplayValue('SYNTHETIC-DOC')

    const deviceSelect = screen.getByRole('combobox', { name: '检查硬件设备' })
    fireEvent.change(deviceSelect, { target: { value: 'SYNTHETIC-DEVICE-2' } })

    fireEvent.click(screen.getByRole('button', { name: '添加检查人员' }))
    fireEvent.click(await screen.findByRole('button', { name: '添加SYNTHETIC-NAME-2' }))
    expect(screen.getAllByTestId(/^inspector-card-/)).toHaveLength(2)

    fireEvent.dragStart(screen.getByTestId('inspector-card-0'))
    fireEvent.drop(screen.getByTestId('inspector-card-1'))
    fireEvent.click(screen.getByRole('button', { name: /保存默认设置/ }))

    await waitFor(() => expect(putMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_DEFAULTS,
      expect.objectContaining({
        values: expect.objectContaining({
          hardware_device: 'SYNTHETIC-DEVICE-2',
          inspector_order: [
            'SYNTHETIC-NAME-2|SYNTHETIC-UNIT-2|SYNTHETIC-POSITION-2|SYNTHETIC-002',
            'SYNTHETIC-NAME|SYNTHETIC-UNIT|SYNTHETIC-POSITION|SYNTHETIC-001',
          ],
        }),
      }),
    ))
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
    expect(getMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_DEFAULTS)).toHaveLength(1)
  })
})
