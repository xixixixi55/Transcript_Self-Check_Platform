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
  document_number: 'SYNTHETIC-DOC',
  document_number_template: { prefix: 'SYN-TEST〔2026〕', suffix: '号' },
  inspection_place: 'SYNTHETIC-PLACE', inspection_method: 'SYNTHETIC-METHOD',
  hardware_device: 'SYNTHETIC-DEVICE',
  inspector_order: ['SYNTHETIC-NAME|SYNTHETIC-UNIT|SYNTHETIC-POSITION|SYNTHETIC-001'],
  disc_number_prefix: 'GP', extraction_method: 'SYNTHETIC-EXTRACTION-METHOD',
  inspection_requirement: 'SYNTHETIC-INSPECTION-REQUIREMENT',
  data_summary: 'SYNTHETIC-DATA-SUMMARY',
  hash_algorithm: 'md5', migration_decision: 'ignored', updated_at: '2026-08-23T00:00:00Z',
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

    expect(await screen.findByDisplayValue('SYN-TEST〔2026〕', {}, { timeout: 5_000 })).toBeTruthy()
    expect(screen.queryByLabelText('委托单位前缀')).toBeNull()
    expect(screen.getByDisplayValue('号')).toBeTruthy()
    expect(screen.getByText('SYN-TEST〔2026〕142号')).toBeTruthy()
    expect((screen.getByLabelText(/^检查要求/) as HTMLTextAreaElement).value).toBe('SYNTHETIC-INSPECTION-REQUIREMENT')
    expect(screen.queryByLabelText('提取方式')).toBeNull()
    expect((screen.getByLabelText(/^数据摘要/) as HTMLTextAreaElement).value).toBe('SYNTHETIC-DATA-SUMMARY')
    expect(screen.getByText('SYNTHETIC-NAME')).toBeTruthy()
    expect(screen.queryByLabelText('光盘编号前缀')).toBeNull()
    expect(screen.queryByText(/当前版本/)).toBeNull()
    expect(screen.queryByText('报告没有识别出真实内容时，系统才会使用这些值预填新案件。')).toBeNull()
    expect(screen.queryByText('新建案件会固化所选算法；历史案件仍按 MD5 显示和校验。')).toBeNull()
    expect(screen.queryByText('按实际落入笔录的顺序排列；清空全部人员表示不设置默认检查人员。')).toBeNull()
    expect(screen.getAllByText('选填')).toHaveLength(3)
    expect(screen.queryByRole('button', { name: '重新加载' })).toBeNull()
    expect(screen.getByRole('button', { name: '保存默认设置' }).textContent).toBe('')
    fireEvent.click(screen.getByRole('radio', { name: 'SHA-256' }))

    fireEvent.change(screen.getByLabelText('文号编号前内容'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('文号编号后内容'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText(/^数据摘要/), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: '移除1' }))
    fireEvent.click(screen.getByRole('button', { name: /保存默认设置/ }))

    await waitFor(() => expect(putMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_DEFAULTS,
      expect.objectContaining({
        expected_revision: 2,
        values: expect.objectContaining({
          document_number: '',
          document_number_template: { prefix: '', suffix: '' },
          inspector_order: [],
          inspection_requirement: 'SYNTHETIC-INSPECTION-REQUIREMENT', hash_algorithm: 'sha256',
          data_summary: '',
        }),
      }),
    ))
    const request = putMock.mock.calls[0]?.[1] as { values?: Record<string, unknown> }
    expect(request.values).not.toHaveProperty('entrust_unit_prefix')
    expect(request.values).not.toHaveProperty('disc_number_prefix')
    expect(request.values).not.toHaveProperty('extraction_method')
    expect(await screen.findByText('笔录默认设置已保存', {}, { timeout: 5_000 })).toBeTruthy()
  }, 10_000)

  it('selects a managed device and reuses inspector cards for add and drag sorting', async () => {
    render(<SharedDefaultsSettingsForm />)
    await screen.findByDisplayValue('SYN-TEST〔2026〕')

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
    await screen.findByDisplayValue('SYN-TEST〔2026〕')

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
