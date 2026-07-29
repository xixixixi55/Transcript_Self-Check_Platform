import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import axios from 'axios'
import { CASE_TASK_POLL_INTERVAL_MS } from '@biji/shared/constants'
import CaseWorkbenchPage from './CaseWorkbenchPage'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const postMock = vi.mocked(axios.post)
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', { writable: true, value: () => ({ matches: false, media: '', onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() }) })
})

const shell = (index: number) => ({
  schema_version: 1, case_id: `case-synthetic-${index}`, case_name: `SYNTHETIC-CASE-${index}`,
  case_summary: 'SYNTHETIC/TEST summary', source_id: `source-synthetic-${index}`,
  parse_task_id: `task-synthetic-${index}`, lifecycle: 'parsing', report_available: false,
  revision: 0, created_at: '2026-01-01T00:00:00+00:00', updated_at: '2026-01-01T00:00:00+00:00',
})

describe('CaseWorkbenchPage', () => {
  let listItems = Array.from({ length: 6 }, (_, i) => shell(i + 1))
  beforeEach(() => {
    vi.clearAllMocks()
    listItems = Array.from({ length: 6 }, (_, i) => shell(i + 1))
    getMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/demo/readiness')) return { data: { data: { items: [
        { key: 'backend', label: '后端服务', status: 'ready', code: null, guidance: '后端服务可用。' },
      ] } } }
      if (url.endsWith('/workbench/cases')) return { data: { data: { items: listItems, offset: 0, limit: 6, has_more: true } } }
      if (url.includes('/workbench/tasks/')) return { data: { data: { task_id: url.split('/').pop(), case_id: 'case-synthetic', kind: 'parse', status: 'running', stage: 'parse', percent: 25, counters: {}, input_revision: 0, attempt: 0, cancel_requested: false, revision: 0 } } }
      throw new Error(`unexpected GET ${url}`)
    })
  })
  afterEach(() => { vi.useRealTimers() })

  it('shows at most six cards, pagination, and a directory-only input', async () => {
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(6))
    expect(document.querySelector('input[type="file"]')).toBeNull()
    expect(screen.getByTitle('2')).toBeTruthy()
    expect(screen.getByText('来源目录授权说明')).toBeTruthy()
    expect(screen.getAllByText('检查删除条件')).toHaveLength(6)
  })

  it('keeps API failures actionable', async () => {
    getMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/demo/readiness')) throw new Error('SYNTHETIC/TEST readiness unavailable')
      if (url.endsWith('/workbench/cases')) throw {
        response: { data: { detail: { code: 'NETWORK_ERROR', message: 'SYNTHETIC/TEST failure' } } },
      }
      throw new Error(`unexpected GET ${url}`)
    })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('SYNTHETIC/TEST failure')).toBeTruthy())
    expect(document.querySelector('.case-workbench-page__toolbar button')).toBeTruthy()
  })

  it('shows a submission response as an immediate case card and sends a directory path', async () => {
    const submitted = { ...shell(99), case_name: 'SYNTHETIC-NEW-CASE' }
    postMock.mockImplementationOnce(async () => {
      listItems = [submitted, ...listItems.slice(0, 5)]
      return { data: { data: { shell: submitted, source: {}, parse_task: {} } } }
    })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(6))
    const inputs = screen.getAllByRole('textbox')
    fireEvent.change(inputs[0], { target: { value: 'C:\\SYNTHETIC\\REPORT' } })
    fireEvent.click(document.querySelector('.case-workbench-page__toolbar button.ant-btn-primary') as HTMLElement)
    await waitFor(() => expect(screen.getAllByText('SYNTHETIC-NEW-CASE').length).toBeGreaterThan(0))
    expect(postMock).toHaveBeenCalledWith(expect.stringContaining('/workbench/cases'), expect.objectContaining({ source_path: 'C:\\SYNTHETIC\\REPORT' }))
  })

  it('shows the backend safe submission error instead of hiding its cause', async () => {
    postMock.mockRejectedValueOnce({
      response: { data: { detail: { code: 'SOURCE_STRUCTURE_INVALID', message: '所选目录不包含可识别的报告结构。' } } },
    })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(6))
    fireEvent.change(screen.getAllByRole('textbox')[0], { target: { value: 'C:\\SYNTHETIC\\REPORT' } })
    fireEvent.click(document.querySelector('.case-workbench-page__toolbar button.ant-btn-primary') as HTMLElement)
    await waitFor(() => expect(screen.getByText('所选目录不包含可识别的报告结构。')).toBeTruthy())
  })

  it('refreshes queued, parsing, and review_ready shell states without remounting', async () => {
    vi.useFakeTimers()
    let listRequests = 0
    let taskRequests = 0
    const queued = { ...shell(1), lifecycle: 'parse_queued' }
    const parsing = shell(1)
    const ready = { ...parsing, lifecycle: 'review_ready', report_available: true }
    getMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/workbench/cases')) {
        listRequests += 1
        const current = listRequests === 1 ? queued : listRequests < 4 ? parsing : ready
        return { data: { data: { items: [current], offset: 0, limit: 6, has_more: false } } }
      }
      if (url.includes('/workbench/tasks/')) {
        taskRequests += 1
        const status = taskRequests === 1 ? 'queued' : taskRequests === 2 ? 'running' : 'succeeded'
        return { data: { data: { task_id: 'task-synthetic-1', case_id: 'case-synthetic-1', kind: 'parse', status, stage: 'parse', percent: null, counters: {}, input_revision: 0, attempt: 0, cancel_requested: false, revision: 0 } } }
      }
      throw new Error(`unexpected GET ${url}`)
    })

    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() })
    expect(document.querySelector('.case-workbench-card')?.textContent).toContain('解析中')
    await act(async () => { await vi.advanceTimersByTimeAsync(CASE_TASK_POLL_INTERVAL_MS) })
    await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() })
    await act(async () => { await vi.advanceTimersByTimeAsync(CASE_TASK_POLL_INTERVAL_MS) })
    await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() })

    expect(listRequests).toBeGreaterThanOrEqual(2)
    expect(taskRequests).toBe(3)
    expect(document.querySelector('a[href="/electronic-inspection/cases/case-synthetic-1"]')).toBeTruthy()
  })
})
