import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS, EXPORT_DIRECTORY_PICKER_TIMEOUT_MS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import { useArchiveCompletion } from './useArchiveCompletion'

vi.mock('axios', () => ({ default: { post: vi.fn() } }))

const postMock = vi.mocked(axios.post)

const MAPPING_RESULT = {
  case_id: 'case-synthetic', task_id: 'task-synthetic', expected_revision: 3,
  lifecycle: 'archive_verified', prefix: 'GP', disc_date: '2026-07-18',
  parts: [{ part_number: 1, disc_number: 'GP20260718-01', disc_date: '2026-07-18' }],
}

const EXPORT_RESULT = {
  case_id: 'case-synthetic', task_id: 'task-synthetic', expected_revision: 3,
  lifecycle: 'exported',
  output: {
    export_path: 'D:\\SYNTHETIC\\out', word_filename: 'case.docx',
    rar_filenames: ['case.part1.rar'], hash_verification_image: 'hash.png',
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
      mapped = await result.current.mapping('case-synthetic', 3, 'GP20260718-01')
    })
    expect(postMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_DISC_MAPPING('case-synthetic'),
      { expected_revision: 3, first_disc_number: 'GP20260718-01' },
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
      exported = await result.current.exportBundle('case-synthetic', 3, 'D:\\SYNTHETIC\\out', 'token-synthetic', '案件名.docx')
    })
    expect(postMock).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_UNIFIED_EXPORT('case-synthetic'),
      {
        expected_revision: 3, export_path: 'D:\\SYNTHETIC\\out',
        directory_token: 'token-synthetic', word_filename: '案件名.docx',
      },
      { timeout: WORKBENCH_REQUEST_TIMEOUT_MS },
    )
    expect(exported).toEqual(EXPORT_RESULT)
  })

  it('surfaces a stable message on failure', async () => {
    postMock.mockRejectedValueOnce({ response: { data: { detail: { code: 'DISC_MAPPING_INCOMPLETE' } } } })
    const { result } = renderHook(() => useArchiveCompletion())
    await act(async () => {
      await result.current.mapping('case-synthetic', 3, 'GP20260718-01').catch(() => undefined)
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
})
