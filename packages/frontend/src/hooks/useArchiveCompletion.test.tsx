import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS, EXPORT_DIRECTORY_PICKER_TIMEOUT_MS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import { unifiedExportRequestTimeoutMs } from '@biji/shared/utils'
import { useArchiveCompletion } from './useArchiveCompletion'

vi.mock('axios', () => ({ default: { post: vi.fn() } }))

const postMock = vi.mocked(axios.post)

const MAPPING_RESULT = {
  case_id: 'case-synthetic', task_id: 'task-synthetic', expected_revision: 3,
  plan_row_revision: 5,
  lifecycle: 'archive_verified', prefix: 'GP', disc_date: '2026-07-18',
  parts: [{ part_number: 1, disc_number: 'GP20260718-01', disc_date: '2026-07-18' }],
}

const EXPORT_RESULT = {
  case_id: 'case-synthetic', task_id: 'task-synthetic', expected_revision: 3,
  lifecycle: 'exported',
  output: {
    export_path: 'D:\\SYNTHETIC\\out', word_filename: 'case.docx',
    rar_filenames: ['case.part1.rar'],
    exported_at: '2026-07-18T00:00:00Z',
  },
}

describe('useArchiveCompletion', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('posts disc mapping and returns the result', async () => {
    postMock.mockResolvedValueOnce({ data: { data: MAPPING_RESULT } } as never)
    const { result } = renderHook(() => useArchiveCompletion())
    let mapped: unknown
    await act(async () => {
      mapped = await result.current.mapping('case-synthetic', 3, 4, 'GP20260718-01')
    })
    expect(postMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_DISC_MAPPING('case-synthetic'),
      {
        expected_revision: 3,
        expected_plan_row_revision: 4,
        first_disc_number: 'GP20260718-01',
      },
      { timeout: WORKBENCH_REQUEST_TIMEOUT_MS },
    )
    expect(mapped).toEqual(MAPPING_RESULT)
    expect(result.current.busy).toBe(false)
  })

  it('posts unified export and returns the result', async () => {
    postMock.mockResolvedValueOnce({ data: { data: EXPORT_RESULT } } as never)
    const { result } = renderHook(() => useArchiveCompletion())
    let exported: unknown
    await act(async () => {
      exported = await result.current.exportBundle(
        'case-synthetic', 3, 'D:\\SYNTHETIC\\out', 'token-synthetic',
        '案件名.docx', [{ size_bytes: 20_000_000_000 }, { size_bytes: 25_000_000_000 }],
      )
    })
    expect(postMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_UNIFIED_EXPORT('case-synthetic'),
      {
        expected_revision: 3, export_path: 'D:\\SYNTHETIC\\out',
        directory_token: 'token-synthetic', word_filename: '案件名.docx',
      },
      { timeout: unifiedExportRequestTimeoutMs(45_000_000_000) },
    )
    expect(exported).toEqual(EXPORT_RESULT)
  })

  it('surfaces a stable message on failure', async () => {
    postMock.mockRejectedValueOnce({ response: { data: { detail: { code: 'DISC_MAPPING_INCOMPLETE' } } } })
    const { result } = renderHook(() => useArchiveCompletion())
    await act(async () => {
      await result.current.mapping('case-synthetic', 3, 4, 'GP20260718-01').catch(() => undefined)
    })
    expect(result.current.error).toBe('操作失败（DISC_MAPPING_INCOMPLETE）。')
  })

  it('asks the backend native picker for an export directory', async () => {
    postMock.mockResolvedValueOnce({ data: { data: { path: 'D:\\SYNTHETIC\\out', token: 'token-synthetic' } } } as never)
    const { result } = renderHook(() => useArchiveCompletion())
    let chosen: unknown
    await act(async () => {
      chosen = await result.current.chooseDirectory()
    })
    expect(postMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY,
      undefined,
      { timeout: EXPORT_DIRECTORY_PICKER_TIMEOUT_MS },
    )
    expect(chosen).toEqual({ path: 'D:\\SYNTHETIC\\out', token: 'token-synthetic' })
  })

  it('returns cancelled when the picker dialog is closed', async () => {
    postMock.mockResolvedValueOnce({ data: { data: { cancelled: true } } } as never)
    const { result } = renderHook(() => useArchiveCompletion())
    let chosen: unknown
    await act(async () => {
      chosen = await result.current.chooseDirectory()
    })
    expect(chosen).toEqual({ cancelled: true })
  })

  it('stays busy until every concurrent operation has settled', async () => {
    let resolveFirst!: (value: unknown) => void
    let resolveSecond!: (value: unknown) => void
    postMock
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveSecond = resolve }))
    const { result } = renderHook(() => useArchiveCompletion())

    let first!: Promise<unknown>
    let second!: Promise<unknown>
    act(() => {
      first = result.current.exportBundle(
        'case-synthetic-1', 1, 'D:\\SYNTHETIC\\one', 'token-1', 'one.docx', [],
      )
      second = result.current.exportBundle(
        'case-synthetic-2', 2, 'D:\\SYNTHETIC\\two', 'token-2', 'two.docx', [],
      )
    })
    expect(result.current.busy).toBe(true)

    await act(async () => {
      resolveFirst({ data: { data: EXPORT_RESULT } })
      await first
    })
    expect(result.current.busy).toBe(true)

    await act(async () => {
      resolveSecond({ data: { data: EXPORT_RESULT } })
      await second
    })
    expect(result.current.busy).toBe(false)
  })
})
