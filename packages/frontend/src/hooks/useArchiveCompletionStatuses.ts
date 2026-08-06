// Layer 10: FE_Hooks — auto-load archive results so workbench cards derive
// completion state without requiring a manual "view result" first.
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
      if (shell.lifecycle !== 'archive_verified') continue
      const summary = summaries[shell.case_id]
      if (!summary || summary.status !== 'succeeded' || results[shell.case_id]) continue
      void loadResult(summary.task_id).then(result => {
        if (active && result.case_id === shell.case_id) {
          setResults(previous => ({ ...previous, [shell.case_id]: result }))
        }
      }).catch(() => undefined)
    }
    return () => { active = false }
  }, [cases, summaries, results, loadResult])
  return results
}
