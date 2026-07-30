// Layer 10: FE_Hooks — task status polling scoped to the current workbench page.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS, CASE_TASK_POLL_INTERVAL_MS } from '@biji/shared/constants'
import type { ArchiveTaskCardSummary, CaseShell, TaskRecord, TaskStatus } from '@biji/shared/types'
import type { WorkbenchError } from './useCaseWorkbench'

const TERMINAL_TASK_STATUSES: ReadonlySet<TaskStatus> = new Set([
  'succeeded', 'failed_retryable', 'failed_terminal', 'cancelled', 'interrupted', 'blocked',
])

export interface TaskRecordsOptions {
  onTaskStatusChange?: (task: TaskRecord) => void
  onPoll?: () => void | Promise<void>
  refreshKey?: number
  cases?: readonly CaseShell[]
}

function getError(error: any): WorkbenchError {
  const detail = error?.response?.data?.detail
  return {
    code: typeof detail?.code === 'string' ? detail.code : 'TASK_STATUS_FAILED',
    message: typeof detail?.message === 'string' ? detail.message : '任务状态暂时无法获取。',
  }
}

export function useTaskRecords(taskIds: readonly string[] = [], options: TaskRecordsOptions = {}) {
  const taskKey = useMemo(() => [...new Set(taskIds)].join('|'), [taskIds.join('|')])
  const ids = useMemo(() => taskKey ? taskKey.split('|') : [], [taskKey])
  const [records, setRecords] = useState<Record<string, TaskRecord>>({})
  const [error, setError] = useState<WorkbenchError | null>(null)
  const refreshRef = useRef<(() => Promise<void>) | null>(null)
  const onTaskStatusChangeRef = useRef(options.onTaskStatusChange)
  const onPollRef = useRef(options.onPoll)
  onTaskStatusChangeRef.current = options.onTaskStatusChange
  onPollRef.current = options.onPoll
  const pollForArchive = options.cases?.some(item => {
    const status = item.archive_task_summary?.status
    return status === 'queued' || status === 'running' || status === 'cancelling' || status === 'blocked'
  }) ?? false

  useEffect(() => {
    let active = true
    let inFlight = false
    let requestSequence = 0
    let timer: number | undefined
    const activeIds = new Set(ids)
    const observedStatuses = new Map<string, TaskStatus>()

    setRecords(current => {
      const next = { ...current }
      Object.keys(next).forEach(id => { if (!activeIds.has(id)) delete next[id] })
      return next
    })

    const refresh = async () => {
      if (!active || (!activeIds.size && !pollForArchive) || inFlight) return
      inFlight = true
      const requestId = ++requestSequence
      const polledIds = [...activeIds]
      const results = await Promise.all(polledIds.map(async id => {
        try {
          const response = await axios.get<{ data: TaskRecord }>(API_ENDPOINTS.WORKBENCH_TASK(id))
          return { id, task: response.data.data }
        } catch (requestError) {
          return { id, error: requestError }
        }
      }))
      await onPollRef.current?.()
      if (!active || requestId !== requestSequence) return

      const successful = results.filter((result): result is { id: string; task: TaskRecord } => 'task' in result)
      const failed = results.filter((result): result is { id: string; error: unknown } => 'error' in result)
      const changedTasks: TaskRecord[] = []
      successful.forEach(({ id, task }) => {
        if (observedStatuses.get(id) !== task.status) changedTasks.push(task)
        observedStatuses.set(id, task.status)
        if (TERMINAL_TASK_STATUSES.has(task.status)) {
          activeIds.delete(id)
        }
      })

      if (failed.length) setError(getError(failed[0].error))
      else setError(null)
      setRecords(current => {
        const next = { ...current }
        successful.forEach(({ id, task }) => { next[id] = task })
        return next
      })
      if (changedTasks.length) onTaskStatusChangeRef.current?.(changedTasks[changedTasks.length - 1])
      if (!activeIds.size && !pollForArchive && timer !== undefined) window.clearInterval(timer)
      inFlight = false
    }

    refreshRef.current = refresh
    setError(null)
    void refresh()
    if (activeIds.size || pollForArchive) {
      timer = window.setInterval(() => { void refresh() }, CASE_TASK_POLL_INTERVAL_MS)
    }
    return () => {
      active = false
      requestSequence += 1
      if (timer !== undefined) window.clearInterval(timer)
      if (refreshRef.current === refresh) refreshRef.current = null
    }
  }, [ids, taskKey, options.refreshKey, pollForArchive])

  const refreshNow = useCallback(() => refreshRef.current?.() ?? Promise.resolve(), [])
  const archiveSummariesByCase = useMemo(
    () => Object.fromEntries(
      (options.cases ?? [])
        .map(item => item.archive_task_summary)
        .filter((summary): summary is ArchiveTaskCardSummary => Boolean(summary))
        .map(summary => [summary.case_id, summary]),
    ) as Record<string, ArchiveTaskCardSummary>,
    [options.cases],
  )
  return { records, archiveSummariesByCase, error, refresh: refreshNow }
}
