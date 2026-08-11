import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import axios from 'axios'
import { CASE_TASK_POLL_INTERVAL_MS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import { unifiedExportRequestTimeoutMs } from '@biji/shared/utils'
import CaseWorkbenchPage from './CaseWorkbenchPage'
import type { ArchiveTaskCardSummary, CaseShell } from '@biji/shared/types'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const postMock = vi.mocked(axios.post)
const deleteMock = vi.mocked(axios.delete)
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', { writable: true, value: () => ({ matches: false, media: '', onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() }) })
})

const shell = (index: number): CaseShell => ({ schema_version: 1, case_id: `case-synthetic-${index}`, case_name: `SYNTHETIC-CASE-${index}`, case_summary: 'SYNTHETIC/TEST summary', source_id: `source-synthetic-${index}`, parse_task_id: `task-synthetic-${index}`, lifecycle: 'parsing', report_available: false, revision: 0, created_at: '2026-01-01T00:00:00+00:00', updated_at: '2026-01-01T00:00:00+00:00' })

const archiveSummary: ArchiveTaskCardSummary = { task_id: 'archive-SYNTHETIC-1', case_id: 'case-synthetic-1', status: 'running', progress_kind: 'workflow_milestone', stage: 'winrar', stage_label: '正在创建 RAR 分卷', stage_index: 4, stage_count: 9, percent: 30, started_at: '2026-07-30T11:42:00Z', updated_at: '2026-07-30T12:00:00Z', finished_at: null, last_heartbeat_at: '2026-07-30T12:00:00Z', output_bytes: 1024, output_volume_count: 1, last_output_change_at: '2026-07-30T12:00:00Z', worker_state: 'owned_running', error_summary: null, allowed_actions: ['cancel'] }

describe('CaseWorkbenchPage', () => {
  let listItems = Array.from({ length: 6 }, (_, i) => shell(i + 1))
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    listItems = Array.from({ length: 6 }, (_, i) => shell(i + 1))
    getMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/workbench/cases')) return { data: { data: { items: listItems, offset: 0, limit: 6, has_more: true } } }
      if (url.includes('/workbench/tasks/')) return { data: { data: { task_id: url.split('/').pop(), case_id: 'case-synthetic', kind: 'parse', status: 'running', stage: 'parse', percent: 25, counters: {}, input_revision: 0, attempt: 0, cancel_requested: false, revision: 0 } } }
      throw new Error(`unexpected GET ${url}`)
    })
  })
  afterEach(() => { vi.useRealTimers() })

  it('shows six cards and hides the upload card when the page is full', async () => {
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(6))
    expect(screen.queryByText('Demo 环境就绪状态')).toBeNull()
    expect(document.querySelector('input[type="file"]')).toBeNull()
    expect(screen.queryByRole('textbox', { name: '报告目录路径' })).toBeNull()
    expect(screen.queryByRole('textbox', { name: '案件名称' })).toBeNull()
    expect(screen.queryByRole('textbox', { name: '案件编号' })).toBeNull()
    expect(screen.queryByRole('button', { name: '上传报告目录' })).toBeNull()
    expect(screen.getAllByLabelText(/案件序号/)).toHaveLength(6)
    expect(screen.getByLabelText('案件序号 1')).toBeTruthy()
    expect(screen.getByLabelText('案件序号 6')).toBeTruthy()
    expect(screen.getByTitle('2')).toBeTruthy()
    expect(screen.getByRole('button', { name: '来源目录校验' }).getAttribute('aria-pressed')).toBe('false')
    expect(screen.getAllByRole('button', { name: '更多操作' })).toHaveLength(6)
  })

  it('keeps API failures actionable', async () => {
    getMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/workbench/cases')) throw {
        response: { data: { detail: { code: 'NETWORK_ERROR', message: 'SYNTHETIC/TEST failure' } } },
      }
      throw new Error(`unexpected GET ${url}`)
    })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('SYNTHETIC/TEST failure')).toBeTruthy())
    expect(document.querySelector('.case-workbench-page__toolbar button')).toBeTruthy()
  })
  it('shows a submission response as an immediate case card through the native directory picker endpoint', async () => {
    listItems = Array.from({ length: 5 }, (_, i) => shell(i + 1))
    const submitted = { ...shell(99), case_name: 'SYNTHETIC-NEW-CASE' }
    postMock.mockImplementationOnce(async () => {
      listItems = [submitted, ...listItems.slice(0, 5)]
      return { data: { data: { shell: submitted, source: {}, parse_task: {} } } }
    })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(5))
    fireEvent.click(screen.getByRole('button', { name: '上传报告目录' }))
    await waitFor(() => expect(screen.getAllByText('SYNTHETIC-NEW-CASE').length).toBeGreaterThan(0))
    expect(postMock).toHaveBeenCalledWith(expect.stringContaining('/workbench/cases/select-directory'), expect.objectContaining({
      source_authorization_enabled: false,
    }))
    expect(postMock.mock.calls[0][1]).not.toHaveProperty('source_path')
  })

  it('persists the compact source authorization button and uses it for submission', async () => {
    listItems = Array.from({ length: 5 }, (_, i) => shell(i + 1))
    const submitted = { ...shell(100), case_name: 'SYNTHETIC-ENABLED-CASE' }
    postMock.mockImplementationOnce(async () => ({
      data: { data: { shell: submitted, source: {}, parse_task: {} } },
    }))
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(5))
    const authorizationButton = screen.getByRole('button', { name: '来源目录校验' })
    expect(authorizationButton.getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(authorizationButton)
    expect(authorizationButton.getAttribute('aria-pressed')).toBe('true')
    expect(window.localStorage.getItem('biji.sourceAuthorization.enabled')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: '上传报告目录' }))
    await waitFor(() => expect(screen.getAllByText('SYNTHETIC-ENABLED-CASE').length).toBeGreaterThan(0))
    expect(postMock).toHaveBeenCalledWith(expect.stringContaining('/workbench/cases'), expect.objectContaining({
      source_authorization_enabled: true,
    }))
  })

  it('restores the persisted source authorization state on the workbench', async () => {
    window.localStorage.setItem('biji.sourceAuthorization.enabled', 'true')
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(6))
    expect(screen.getByRole('button', { name: '来源目录校验' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('shows the backend safe submission error instead of hiding its cause', async () => {
    listItems = Array.from({ length: 5 }, (_, i) => shell(i + 1))
    postMock.mockRejectedValueOnce({
      response: { data: { detail: { code: 'SOURCE_STRUCTURE_INVALID', message: '所选目录不包含可识别的报告结构。' } } },
    })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(5))
    fireEvent.click(screen.getByRole('button', { name: '上传报告目录' }))
    await waitFor(() => expect(screen.getByText('所选目录不包含可识别的报告结构。')).toBeTruthy())
  })

  it('keeps the workbench unchanged when the native directory picker is cancelled', async () => {
    listItems = Array.from({ length: 5 }, (_, i) => shell(i + 1))
    postMock.mockResolvedValueOnce({ data: { data: { cancelled: true } } })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(5))
    fireEvent.click(screen.getByRole('button', { name: '上传报告目录' }))
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      expect.stringContaining('/workbench/cases/select-directory'),
      expect.not.objectContaining({ source_path: expect.anything() }),
    ))
    expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(5)
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

  it('renders the backend card summary through the existing task polling source', async () => {
    listItems = [{ ...shell(1), lifecycle: 'review_ready', report_available: true, archive_task_summary: archiveSummary }]
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('progressbar', {
      name: '任务正在运行：正在创建 RAR 分卷',
    })).toBeTruthy())
    expect(screen.getByRole('button', { name: '取消归档' })).toBeTruthy()
  })

  it('uses backend details and revision for archive cancel without duplicate submission', async () => {
    listItems = [{ ...shell(1), lifecycle: 'review_ready', report_available: true, archive_task_summary: archiveSummary }]
    getMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/workbench/cases')) return { data: { data: { items: listItems, offset: 0, limit: 6, has_more: false } } }
      if (url.endsWith('/archive-SYNTHETIC-1/details')) return { data: { data: { ...archiveSummary, revision: 7, created_at: archiveSummary.updated_at } } }
      if (url.includes('/workbench/tasks/')) return { data: { data: { task_id: 'task-synthetic-1', case_id: 'case-synthetic-1', kind: 'parse', status: 'succeeded', stage: 'parse', percent: null, counters: {}, input_revision: 0, attempt: 0, cancel_requested: false, revision: 0 } } }
      throw new Error(`unexpected GET ${url}`)
    })
    postMock.mockResolvedValue({ data: { data: { ...archiveSummary, status: 'cancelling' } } })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    const button = await screen.findByRole('button', { name: '取消归档' })
    fireEvent.click(button)
    fireEvent.click(button)
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(expect.stringContaining('/archive-SYNTHETIC-1/cancel'), { expected_revision: 7 }, { timeout: WORKBENCH_REQUEST_TIMEOUT_MS }))
    expect(postMock).toHaveBeenCalledTimes(1)
  })

  it('cancels the deletion confirmation without calling the delete API', async () => {
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(6))
    fireEvent.click(screen.getAllByRole('button', { name: /^删\s*除$/ })[0])
    expect(screen.getByText('确认删除吗？')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^取\s*消$/ }))
    expect(deleteMock).not.toHaveBeenCalled()
    expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(6)
  })

  it('deletes the case after confirmation and refreshes the workbench list', async () => {
    deleteMock.mockImplementationOnce(async () => {
      listItems = []
      return { data: { data: { case_id: 'case-synthetic-1', deleted: true } } }
    })
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(6))
    fireEvent.click(screen.getAllByRole('button', { name: /^删\s*除$/ })[0])
    fireEvent.click(screen.getByRole('button', { name: /确\s*认/ }))

    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith(
      expect.stringContaining('/workbench/cases/case-synthetic-1'),
      { timeout: WORKBENCH_REQUEST_TIMEOUT_MS },
    ))
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(0))
    expect(screen.getByRole('button', { name: '上传报告目录' })).toBeTruthy()
  })

  it('shows only the upload card when the workbench has no cases', async () => {
    listItems = []
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('button', { name: '上传报告目录' })).toBeTruthy())
    expect(document.querySelector('.ant-empty')).toBeNull()
  })

  it('places the upload card inside the grid beside cases when the page is not full', async () => {
    listItems = [shell(1)]
    render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
    await waitFor(() => expect(document.querySelectorAll('.case-workbench-card')).toHaveLength(1))
    expect(screen.getByLabelText('案件序号 1')).toBeTruthy()
    expect(document.querySelector('.case-workbench-grid')?.contains(screen.getByRole('button', { name: '上传报告目录' }))).toBe(true)
  })
it('exports a completed archive bundle directly from the card', async () => {
  listItems = [{ ...shell(1), lifecycle: 'exported', report_available: true, revision: 3, archive_task_summary: { ...archiveSummary, status: 'succeeded', stage: 'completed', stage_label: '归档完成', stage_index: 9, stage_count: 9, percent: 100, output_bytes: null, finished_at: '2026-07-30T12:00:00Z', allowed_actions: ['view_result'] } }]
  const archiveResult = { task_id: 'archive-SYNTHETIC-1', case_id: 'case-synthetic-1', manifest_id: 'manifest-synthetic', verified_slots: [], assets: [], parts: [{ part_id: 'part-1', filename: 'SYNTHETIC.part1.rar', size_bytes: 45_000_000_000, md5: 'a'.repeat(32), disc_number: 'GP20260730-01', disc_date: '2026-07-30' }], finished_at: '2026-07-30T12:00:00Z' }
  getMock.mockImplementation(async (url: string) => {
    if (url.endsWith('/workbench/cases')) return { data: { data: { items: listItems, offset: 0, limit: 6, has_more: false } } }
    if (url.includes('/result')) return { data: { data: archiveResult } }
    if (url.includes('/workbench/tasks/')) return { data: { data: { task_id: 'task-synthetic-1', case_id: 'case-synthetic-1', kind: 'parse', status: 'succeeded', stage: 'parse', percent: null, counters: {}, input_revision: 0, attempt: 0, cancel_requested: false, revision: 0 } } }
    throw new Error(`unexpected GET ${url}`)
  })
  postMock.mockImplementation(async (url: string, body?: unknown) => {
    if (url.endsWith('/select-export-directory')) return { data: { data: { path: 'D:\SYNTHETIC\EXPORT', token: 'token-synthetic' } } }
    if (url.endsWith('/export-bundle')) return { data: { data: { case_id: 'case-synthetic-1', task_id: 'archive-SYNTHETIC-1', expected_revision: (body as { expected_revision: number }).expected_revision, lifecycle: 'exported', output: { export_path: 'D:\SYNTHETIC\EXPORT', word_filename: 'out.docx', rar_filenames: ['SYNTHETIC.part1.rar'], hash_verification_image: 'hash.png', exported_at: '2026-07-30T12:01:00Z' } } } }
    return { data: { data: {} } }
  })
  render(<MemoryRouter><CaseWorkbenchPage /></MemoryRouter>)
  const exportButton = await screen.findByRole('button', { name: '统一导出' })
  expect(screen.queryByRole('button', { name: '查看结果' })).toBeNull()
  fireEvent.click(exportButton)
  const nameInput = (await screen.findByRole('textbox', { name: 'Word 下载文件名' })) as HTMLInputElement
  expect(nameInput.value).toBe('SYNTHETIC-CASE-1.docx')
  fireEvent.change(nameInput, { target: { value: '自定义案件.docx' } }); fireEvent.click(screen.getByRole('button', { name: '开始导出' }))
  await waitFor(() => expect(postMock).toHaveBeenCalledWith(expect.stringContaining('/export-bundle'), { expected_revision: 3, export_path: 'D:\SYNTHETIC\EXPORT', directory_token: 'token-synthetic', word_filename: '自定义案件.docx' }, { timeout: unifiedExportRequestTimeoutMs(45_000_000_000) }))
  expect(await screen.findByText(/已导出至：D:\SYNTHETIC\EXPORT/)).toBeTruthy()
})
})
