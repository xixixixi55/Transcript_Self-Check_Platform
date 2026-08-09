import { useCallback, useEffect, useState } from 'react'
import type { ArchiveTaskCardSummary, ArchiveTaskResult } from '@biji/shared/types'

export interface CompletedArchiveState {
  result: ArchiveTaskResult | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useCompletedArchiveResult(
  summary: ArchiveTaskCardSummary | null | undefined,
  loadResult: (taskId: string) => Promise<ArchiveTaskResult>,
): CompletedArchiveState {
  const [state, setState] = useState<Omit<CompletedArchiveState, 'reload'>>({ result: null, loading: false, error: null })
  const [reloadVersion, setReloadVersion] = useState(0)
  const reload = useCallback(() => setReloadVersion(value => value + 1), [])

  useEffect(() => {
    let active = true
    setState({ result: null, loading: false, error: null })
    if (!summary || summary.status !== 'succeeded') return () => { active = false }
    setState(current => ({
      result: current.result?.task_id === summary.task_id ? current.result : null,
      loading: true,
      error: null,
    }))
    void loadResult(summary.task_id).then(result => {
      if (active) setState({ result, loading: false, error: null })
    }).catch(() => {
      if (active) setState({ result: null, loading: false, error: '已完成归档结果暂时无法读取。' })
    })
    return () => { active = false }
  }, [loadResult, reloadVersion, summary?.status, summary?.task_id])

  return { ...state, reload }
}
