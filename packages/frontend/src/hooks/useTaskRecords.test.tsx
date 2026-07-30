import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { CASE_TASK_POLL_INTERVAL_MS } from '@biji/shared/constants'
import type { ArchiveTaskCardSummary, TaskRecord, TaskStatus } from '@biji/shared/types'
import { useTaskRecords } from './useTaskRecords'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))

const getMock = vi.mocked(axios.get)

function task(taskId: string, status: TaskStatus): TaskRecord {
  return {
    schema_version: 1, task_id: taskId, case_id: `case-${taskId}`, kind: 'parse', status,
    stage: 'parse', percent: null, counters: {}, input_revision: 0, attempt: 0,
    cancel_requested: false, revision: 0, created_at: '2026-01-01T00:00:00Z',
  }
}

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}

describe('useTaskRecords', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => { vi.useRealTimers() })

  it('updates multiple cases independently and stops polling terminal tasks', async () => {
    const counts: Record<string, number> = {}
    const statusChanged = vi.fn()
    getMock.mockImplementation(async (url: string) => {
      const id = url.split('/').pop() || ''
      const count = counts[id] || 0
      counts[id] = count + 1
      const status = id === 'task-a'
        ? (count === 0 ? 'queued' : 'succeeded')
        : (count === 0 ? 'running' : 'failed_retryable')
      return { data: { data: task(id, status) } }
    })

    const view = renderHook(() => useTaskRecords(['task-a', 'task-b'], { onTaskStatusChange: statusChanged }))
    await act(async () => { await flushPromises() })
    expect(view.result.current.records['task-a'].status).toBe('queued')
    expect(view.result.current.records['task-b'].status).toBe('running')

    await act(async () => { await vi.advanceTimersByTimeAsync(CASE_TASK_POLL_INTERVAL_MS) })
    expect(view.result.current.records['task-a'].status).toBe('succeeded')
    expect(view.result.current.records['task-b'].status).toBe('failed_retryable')
    expect(statusChanged.mock.calls.map(([value]) => value.status)).toEqual(['running', 'failed_retryable'])

    const callsAfterTerminal = getMock.mock.calls.length
    await act(async () => { await vi.advanceTimersByTimeAsync(CASE_TASK_POLL_INTERVAL_MS * 2) })
    expect(getMock.mock.calls.length).toBe(callsAfterTerminal)
  })

  it('keeps the last task state after a network failure and recovers next round', async () => {
    let count = 0
    const statusChanged = vi.fn()
    getMock.mockImplementation(async (url: string) => {
      count += 1
      if (count === 2) throw { response: { data: { detail: { code: 'NETWORK_ERROR', message: 'SYNTHETIC/TEST network failure' } } } }
      return { data: { data: task(url.split('/').pop() || 'task-a', count >= 3 ? 'succeeded' : 'running') } }
    })

    const view = renderHook(() => useTaskRecords(['task-a'], { onTaskStatusChange: statusChanged }))
    await act(async () => { await flushPromises() })
    await act(async () => { await vi.advanceTimersByTimeAsync(CASE_TASK_POLL_INTERVAL_MS) })
    expect(view.result.current.records['task-a'].status).toBe('running')
    expect(view.result.current.error?.code).toBe('NETWORK_ERROR')

    await act(async () => { await vi.advanceTimersByTimeAsync(CASE_TASK_POLL_INTERVAL_MS) })
    expect(view.result.current.records['task-a'].status).toBe('succeeded')
    expect(view.result.current.error).toBeNull()
    expect(statusChanged).toHaveBeenCalledWith(expect.objectContaining({ status: 'succeeded' }))
  })

  it('ignores a response from an effect that was replaced by a newer request', async () => {
    let resolveFirst: ((value: unknown) => void) | undefined
    let resolveSecond: ((value: unknown) => void) | undefined
    getMock
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveSecond = resolve }))

    const view = renderHook(({ refreshKey }) => useTaskRecords(['task-a'], { refreshKey }), { initialProps: { refreshKey: 0 } })
    await act(async () => { await flushPromises() })
    view.rerender({ refreshKey: 1 })
    await act(async () => { await flushPromises() })
    await act(async () => {
      resolveSecond?.({ data: { data: task('task-a', 'succeeded') } })
      await flushPromises()
    })
    expect(view.result.current.records['task-a'].status).toBe('succeeded')

    await act(async () => {
      resolveFirst?.({ data: { data: task('task-a', 'running') } })
      await flushPromises()
    })
    expect(view.result.current.records['task-a'].status).toBe('succeeded')
  })

  it('cleans up the timer when the page is unmounted', async () => {
    getMock.mockResolvedValue({ data: { data: task('task-a', 'running') } })
    const view = renderHook(() => useTaskRecords(['task-a']))
    await act(async () => { await flushPromises() })
    const callsBeforeUnmount = getMock.mock.calls.length
    view.unmount()
    await act(async () => { await vi.advanceTimersByTimeAsync(CASE_TASK_POLL_INTERVAL_MS * 2) })
    expect(getMock.mock.calls.length).toBe(callsBeforeUnmount)
  })

  it('maps injected archive summary fixtures without creating another polling source', async () => {
    getMock.mockResolvedValue({ data: { data: task('task-a', 'running') } })
    const archiveSummary: ArchiveTaskCardSummary = {
      task_id: 'archive-SYNTHETIC',
      case_id: 'case-task-a',
      status: 'running',
      progress_kind: 'workflow_milestone',
      stage: 'winrar',
      stage_label: '正在创建 RAR 分卷',
      stage_index: 4,
      stage_count: 9,
      percent: 30,
      started_at: '2026-07-30T11:42:00Z',
      updated_at: '2026-07-30T12:00:00Z',
      finished_at: null,
      last_heartbeat_at: '2026-07-30T12:00:00Z',
      output_bytes: 1024,
      output_volume_count: 1,
      last_output_change_at: '2026-07-30T12:00:00Z',
      worker_state: 'owned_running',
      error_summary: null,
      allowed_actions: ['cancel'],
    }
    const view = renderHook(() => useTaskRecords(
      ['task-a'],
      { archiveSummaryFixtures: [archiveSummary] },
    ))
    await act(async () => { await flushPromises() })

    expect(view.result.current.archiveSummariesByCase['case-task-a']).toEqual(archiveSummary)
    expect(getMock).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
    expect(getMock).toHaveBeenCalledTimes(1 + Math.floor(60_000 / CASE_TASK_POLL_INTERVAL_MS))
  })
})
