import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { useCaseWorkbench } from './useCaseWorkbench'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const detail = {
  shell: { case_id: 'case-synthetic', revision: 1 },
  draft: null,
  source: { source_id: 'source-synthetic', access_status: 'pending' },
  parse_task: { task_id: 'task-synthetic', status: 'succeeded' },
} as any

describe('useCaseWorkbench detail reload', () => {
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
})
