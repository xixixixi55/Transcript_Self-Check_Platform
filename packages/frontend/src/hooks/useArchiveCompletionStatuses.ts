// 第 10 层：FE_Hooks — 自动加载归档结果，使工作台卡片无需先手动“查看结果”
// 即可推导完成状态。
import { useEffect, useState } from 'react'
import type { ArchiveTaskCardSummary, ArchiveTaskResult, CaseShell } from '@biji/shared/types'

export function useArchiveCompletionStatuses(
  cases: CaseShell[],
  summaries: Record<string, ArchiveTaskCardSummary>,
  loadResult: (taskId: string) => Promise<ArchiveTaskResult>,
): Record<string, ArchiveTaskResult> {
  const [results, setResults] = useState<Record<string, ArchiveTaskResult>>({})
  useEffect(() => {
    let active = true
    for (const shell of cases) {
      if (shell.lifecycle !== 'archive_verified' && shell.lifecycle !== 'exported') continue
      const summary = summaries[shell.case_id]
      const cached = results[shell.case_id]
      if (!summary || summary.status !== 'succeeded' || cached?.task_id === summary.task_id) continue
      void loadResult(summary.task_id).then(result => {
        if (active && result.case_id === shell.case_id && result.task_id === summary.task_id) {
          setResults(previous => ({ ...previous, [shell.case_id]: result }))
        }
      }).catch(() => undefined)
    }
    return () => { active = false }
  }, [cases, summaries, results, loadResult])
  return results
}
