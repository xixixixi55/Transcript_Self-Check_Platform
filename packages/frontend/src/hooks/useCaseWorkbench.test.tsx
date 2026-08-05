import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import { useCaseWorkbench } from './useCaseWorkbench'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const postMock = vi.mocked(axios.post)
const deleteMock = vi.mocked(axios.delete)
const detail = {
  shell: { case_id: 'case-synthetic', revision: 1 },
  draft: null,
  source: { source_id: 'source-synthetic', access_status: 'pending' },
  parse_task: { task_id: 'task-synthetic', status: 'succeeded' },
} as any

describe('useCaseWorkbench detail reload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
  })

  it('keeps the editor out of loading state during background source polling', async () => {
    getMock.mockResolvedValueOnce({ data: { data: detail } })
    const view = renderHook(() => useCaseWorkbench('case-synthetic'))
    await waitFor(() => expect(view.result.current.detailLoading).toBe(false))

    let release!: () => void
    const blocked = new Promise<void>(resolve => { release = resolve })
    getMock.mockImplementationOnce(async () => {
      await blocked
      return { data: { data: detail } }
    })
    let reload!: Promise<unknown>
    await act(async () => {
      reload = view.result.current.reloadDetail('case-synthetic', { background: true })
      await Promise.resolve()
    })
    expect(view.result.current.detailLoading).toBe(false)
    release()
    await act(async () => { await reload })
  })

  it('sends the persisted source authorization mode when submitting a case', async () => {
    window.localStorage.setItem('biji.sourceAuthorization.enabled', 'true')
    getMock.mockResolvedValue({ data: { data: { items: [], offset: 0, limit: 6, has_more: false } } })
    postMock.mockResolvedValue({ data: { data: {
      shell: { case_id: 'case-synthetic', revision: 0 }, source: {}, parse_task: {},
    } } })
    const view = renderHook(() => useCaseWorkbench())
    await waitFor(() => expect(getMock).toHaveBeenCalled())

    await act(async () => { await view.result.current.submitCase('C:\\SYNTHETIC\\REPORT') })

    expect(postMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_CASES,
      expect.objectContaining({ source_authorization_enabled: true }),
    )
  })

  it('submits the native directory selection through a pathless request', async () => {
    getMock.mockResolvedValue({ data: { data: { items: [], offset: 0, limit: 6, has_more: false } } })
    postMock.mockResolvedValue({ data: { data: {
      shell: { case_id: 'case-synthetic', revision: 0 }, source: {}, parse_task: {}, shared_defaults: {},
    } } })
    const view = renderHook(() => useCaseWorkbench())
    await waitFor(() => expect(getMock).toHaveBeenCalled())

    await act(async () => { await view.result.current.selectDirectoryAndSubmitCase({ caseName: 'SYNTHETIC-PICKED' }) })

    expect(postMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_SELECT_DIRECTORY_CASE,
      expect.objectContaining({ case_name: 'SYNTHETIC-PICKED', source_authorization_enabled: false }),
    )
    expect(postMock.mock.calls[0][1]).not.toHaveProperty('source_path')
  })

  it('returns null when the native directory selection is cancelled', async () => {
    getMock.mockResolvedValue({ data: { data: { items: [], offset: 0, limit: 6, has_more: false } } })
    postMock.mockResolvedValue({ data: { data: { cancelled: true } } })
    const view = renderHook(() => useCaseWorkbench())
    await waitFor(() => expect(getMock).toHaveBeenCalled())

    let result: unknown
    await act(async () => { result = await view.result.current.selectDirectoryAndSubmitCase() })

    expect(result).toBeNull()
  })

  it('deletes a case through the workbench delete endpoint', async () => {
    getMock.mockResolvedValue({ data: { data: { items: [], offset: 0, limit: 6, has_more: false } } })
    deleteMock.mockResolvedValue({ data: { data: { case_id: 'case-synthetic', deleted: true } } })
    const view = renderHook(() => useCaseWorkbench())
    await waitFor(() => expect(getMock).toHaveBeenCalled())

    let result!: { case_id: string; deleted: true }
    await act(async () => {
      result = await view.result.current.deleteCase('case-synthetic')
    })

    expect(deleteMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_DELETE_CASE('case-synthetic'))
    expect(result).toEqual({ case_id: 'case-synthetic', deleted: true })
  })
})
