// 第 10 层：FE_Hooks — 保存尚未写入案件的快捷检材输入草稿。
import { useCallback, useEffect, useState } from 'react'

const STORAGE_PREFIX = 'biji.guidedReview.quickEvidenceBatchDraft.v1.'
const DRAFT_VERSION = 1
const MAX_DRAFT_LENGTH = 5000

interface QuickEvidenceBatchDraft {
  version: typeof DRAFT_VERSION
  caseId: string
  value: string
}

export function quickEvidenceBatchDraftStorageKey(caseId: string): string {
  return `${STORAGE_PREFIX}${encodeURIComponent(caseId)}`
}

function readQuickEvidenceBatchDraft(caseId: string): string {
  if (typeof window === 'undefined' || !caseId) return ''
  try {
    const serialized = window.localStorage.getItem(quickEvidenceBatchDraftStorageKey(caseId))
    if (!serialized) return ''
    const candidate = JSON.parse(serialized) as Partial<QuickEvidenceBatchDraft>
    if (candidate.version !== DRAFT_VERSION || candidate.caseId !== caseId
      || typeof candidate.value !== 'string' || candidate.value.length > MAX_DRAFT_LENGTH) return ''
    return candidate.value
  } catch {
    return ''
  }
}

function writeQuickEvidenceBatchDraft(caseId: string, value: string): void {
  if (typeof window === 'undefined' || !caseId) return
  try {
    const key = quickEvidenceBatchDraftStorageKey(caseId)
    if (!value) {
      window.localStorage.removeItem(key)
      return
    }
    const draft: QuickEvidenceBatchDraft = { version: DRAFT_VERSION, caseId, value }
    window.localStorage.setItem(key, JSON.stringify(draft))
  } catch {
    // 禁用、配额不足或隐私模式下只保留当前页面内存草稿，不阻塞办理。
  }
}

export function useQuickEvidenceBatchDraft(caseId: string) {
  const [draft, setDraft] = useState(() => ({
    caseId,
    value: readQuickEvidenceBatchDraft(caseId),
  }))
  const value = draft.caseId === caseId ? draft.value : readQuickEvidenceBatchDraft(caseId)

  useEffect(() => {
    setDraft(previous => previous.caseId === caseId
      ? previous
      : { caseId, value: readQuickEvidenceBatchDraft(caseId) })
  }, [caseId])

  const setValue = useCallback((nextValue: string) => {
    const boundedValue = nextValue.slice(0, MAX_DRAFT_LENGTH)
    setDraft({ caseId, value: boundedValue })
    writeQuickEvidenceBatchDraft(caseId, boundedValue)
  }, [caseId])

  const clear = useCallback(() => {
    setDraft({ caseId, value: '' })
    writeQuickEvidenceBatchDraft(caseId, '')
  }, [caseId])

  return { value, setValue, clear }
}
