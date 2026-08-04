import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { DemoReadinessNotice } from './DemoReadinessNotice'
import { SourceReselectionPanel } from './SourceReselectionPanel'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))
const getMock = vi.mocked(axios.get)

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: () => ({
      matches: false, media: '', onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  })
})

describe('Demo readiness and source guidance', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders only the safe status, code, and guidance projection', async () => {
    getMock.mockResolvedValue({
      data: { data: { items: [
        { key: 'backend', label: '后端服务', status: 'ready', code: null, guidance: '后端服务可用。' },
        { key: 'winrar', label: 'WinRAR', status: 'unavailable', code: 'WINRAR_UNAVAILABLE', guidance: '请检查服务器配置。' },
        { key: 'archive_output', label: '归档输出根', status: 'unknown', code: 'DEMO_ARCHIVE_OUTPUT_UNKNOWN', guidance: '当前无法确认。' },
      ] } },
    })
    render(<DemoReadinessNotice />)

    await waitFor(() => expect(screen.getByText('已就绪')).toBeTruthy())
    expect(screen.getByText('当前不可用')).toBeTruthy()
    expect(screen.getByText('无法确认')).toBeTruthy()
    expect(document.body.textContent).not.toContain('C:\\')
  })

  it.each([
    ['ARCHIVE_INPUT_ROOT_NOT_ALLOWED', '所选报告目录未获授权。'],
    ['SOURCE_ACCESS_DENIED', '所选报告目录当前无法访问。'],
    ['SOURCE_STRUCTURE_INVALID', '所选目录不包含可识别的报告结构。'],
  ])('keeps replacement error %s distinct and safe', async (code, message) => {
    const onReselect = vi.fn().mockRejectedValue({
      response: { data: { detail: { code, message } } },
    })
    render(<SourceReselectionPanel required onReselect={onReselect} />)

    fireEvent.change(screen.getByLabelText('重新选择报告目录路径'), {
      target: { value: 'C:\\SYNTHETIC\\REPORT' },
    })
    fireEvent.click(screen.getByRole('button', { name: '重新登记来源目录' }))

    await waitFor(() => expect(screen.getByText(message)).toBeTruthy())
    expect(document.body.textContent).not.toContain('C:\\SYNTHETIC\\REPORT')
  })
})
