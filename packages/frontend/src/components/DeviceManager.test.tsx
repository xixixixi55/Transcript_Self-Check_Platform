import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import DeviceManager from './DeviceManager'

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const getMock = vi.mocked(axios.get)
const postMock = vi.mocked(axios.post)
const putMock = vi.mocked(axios.put)

const devices = [
  {
    id: 'device-SYNTHETIC-1', name: 'SYNTHETIC FL-901', company: 'SYNTHETIC美亚柏科',
  },
  {
    id: 'device-SYNTHETIC-legacy', name: 'SYNTHETIC LEGACY', company: '',
  },
]

beforeAll(() => {
  const getComputedStyle = window.getComputedStyle.bind(window)
  vi.spyOn(window, 'getComputedStyle').mockImplementation(element => getComputedStyle(element))
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
  getMock.mockResolvedValue({ data: { data: devices } })
  postMock.mockResolvedValue({ data: { success: true } })
  putMock.mockResolvedValue({ data: { success: true } })
})

describe('DeviceManager company field', () => {
  it('展示设备所属公司，并兼容旧记录的待补充状态', async () => {
    render(<DeviceManager />)

    expect(await screen.findByText('SYNTHETIC美亚柏科')).toBeTruthy()
    expect(screen.getByText('待补充')).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: '所属公司' })).toBeTruthy()
    expect(screen.queryByRole('columnheader', { name: '型号' })).toBeNull()
    expect(screen.queryByRole('columnheader', { name: '描述' })).toBeNull()
  })

  it('新增设备时要求所属公司并将其提交到设备 API', async () => {
    render(<DeviceManager />)
    await screen.findByText('SYNTHETIC FL-901')
    fireEvent.click(screen.getByRole('button', { name: /添加设备/ }))
    fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'SYNTHETIC NEW DEVICE' } })
    fireEvent.click(screen.getByRole('button', { name: /保\s*存/ }))

    expect(await screen.findByText('请输入所属公司')).toBeTruthy()
    expect(postMock).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('所属公司'), { target: { value: 'SYNTHETIC COMPANY' } })
    fireEvent.click(screen.getByRole('button', { name: /保\s*存/ }))
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.DEVICES, {
      name: 'SYNTHETIC NEW DEVICE', company: 'SYNTHETIC COMPANY',
    }))
  })

  it('编辑设备时回填并更新所属公司', async () => {
    render(<DeviceManager />)
    await screen.findByText('SYNTHETIC FL-901')
    fireEvent.click(screen.getAllByRole('button', { name: /编辑/ })[0])

    expect((screen.getByLabelText('所属公司') as HTMLInputElement).value).toBe('SYNTHETIC美亚柏科')
    fireEvent.change(screen.getByLabelText('所属公司'), { target: { value: 'SYNTHETIC UPDATED COMPANY' } })
    fireEvent.click(screen.getByRole('button', { name: /保\s*存/ }))

    await waitFor(() => expect(putMock).toHaveBeenCalledWith(
      `${API_ENDPOINTS.DEVICES}/device-SYNTHETIC-1`,
      expect.objectContaining({ company: 'SYNTHETIC UPDATED COMPANY' }),
    ))
  })
})
