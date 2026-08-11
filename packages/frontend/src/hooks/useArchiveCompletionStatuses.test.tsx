import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ArchiveTaskCardSummary, ArchiveTaskResult, CaseShell } from '@biji/shared/types'
import { useArchiveCompletionStatuses } from './useArchiveCompletionStatuses'

const CASE = {
  case_id: 'case-synthetic',
  lifecycle: 'exported',
} as CaseShell

function summary(taskId: string): ArchiveTaskCardSummary {
  return {
    task_id: taskId,
    case_id: CASE.case_id,
    status: 'succeeded',
  } as ArchiveTaskCardSummary
}

function result(taskId: string, sizeBytes: number): ArchiveTaskResult {
  return {
    task_id: taskId,
    case_id: CASE.case_id,
    parts: [{ size_bytes: sizeBytes }],
  } as ArchiveTaskResult
}

describe('useArchiveCompletionStatuses', () => {
  it('loads exported results and replaces a cached result when the current task changes', async () => {
    const loadResult = vi.fn(async (taskId: string) => (
      taskId === 'task-new'
        ? result(taskId, 45_000_000_000)
        : result(taskId, 4_000_000_000)
    ))
    const { result: hookResult, rerender } = renderHook(
      ({ summaries }) => useArchiveCompletionStatuses([CASE], summaries, loadResult),
      { initialProps: { summaries: { [CASE.case_id]: summary('task-old') } } },
    )

    await waitFor(() => expect(hookResult.current[CASE.case_id]?.task_id).toBe('task-old'))

    rerender({ summaries: { [CASE.case_id]: summary('task-new') } })

    await waitFor(() => expect(hookResult.current[CASE.case_id]?.task_id).toBe('task-new'))
    expect(hookResult.current[CASE.case_id]?.parts[0]?.size_bytes).toBe(45_000_000_000)
    expect(loadResult).toHaveBeenNthCalledWith(1, 'task-old')
    expect(loadResult).toHaveBeenNthCalledWith(2, 'task-new')
  })
})
