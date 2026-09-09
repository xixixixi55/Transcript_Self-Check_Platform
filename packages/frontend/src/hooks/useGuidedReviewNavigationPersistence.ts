// 第 10 层：FE_Hooks — 只保存可重建的引导步骤参考，不保存案件字段值。
const STORAGE_PREFIX = 'biji.guidedReview.navigation.v1.'
const CHECKPOINT_VERSION = 1
const MAX_STORED_STEPS = 100
const MAX_REFERENCE_LENGTH = 240

export interface GuidedReviewNavigationStepReference {
  actionId: string
  targetId?: string
}

export interface GuidedReviewNavigationCheckpoint {
  version: typeof CHECKPOINT_VERSION
  caseId: string
  entries: GuidedReviewNavigationStepReference[]
  index: number
}

export interface GuidedReviewNavigationState<TAction> {
  caseId: string
  entries: TAction[]
  index: number
}

interface NavigableAction {
  id: string
  pendingItem?: { targetId: string }
}

export function guidedReviewNavigationStorageKey(caseId: string): string {
  return `${STORAGE_PREFIX}${encodeURIComponent(caseId)}`
}

function isBoundedString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= MAX_REFERENCE_LENGTH
}

function parseStepReference(value: unknown): GuidedReviewNavigationStepReference | null {
  if (!value || typeof value !== 'object') return null
  const candidate = value as Record<string, unknown>
  if (!isBoundedString(candidate.actionId)) return null
  if (candidate.targetId !== undefined && !isBoundedString(candidate.targetId)) return null
  return {
    actionId: candidate.actionId,
    ...(typeof candidate.targetId === 'string' ? { targetId: candidate.targetId } : {}),
  }
}

export function readGuidedReviewNavigationCheckpoint(
  caseId: string,
): GuidedReviewNavigationCheckpoint | null {
  if (typeof window === 'undefined' || !caseId) return null
  try {
    const serialized = window.localStorage.getItem(guidedReviewNavigationStorageKey(caseId))
    if (!serialized) return null
    const candidate = JSON.parse(serialized) as Record<string, unknown>
    if (candidate.version !== CHECKPOINT_VERSION || candidate.caseId !== caseId
      || !Array.isArray(candidate.entries) || candidate.entries.length > MAX_STORED_STEPS
      || !Number.isInteger(candidate.index)) return null
    const entries = candidate.entries.map(parseStepReference)
    if (entries.some(entry => entry === null)) return null
    const index = candidate.index as number
    if (entries.length === 0 || index < 0 || index >= entries.length) return null
    return {
      version: CHECKPOINT_VERSION,
      caseId,
      entries: entries as GuidedReviewNavigationStepReference[],
      index,
    }
  } catch {
    return null
  }
}

export function writeGuidedReviewNavigationCheckpoint(
  caseId: string,
  entries: GuidedReviewNavigationStepReference[],
  index: number,
): void {
  if (typeof window === 'undefined' || !caseId) return
  try {
    const key = guidedReviewNavigationStorageKey(caseId)
    if (entries.length === 0) {
      window.localStorage.removeItem(key)
      return
    }
    const boundedEntries = entries.slice(-MAX_STORED_STEPS)
    const removedCount = entries.length - boundedEntries.length
    const boundedIndex = Math.max(0, Math.min(boundedEntries.length - 1, index - removedCount))
    const checkpoint: GuidedReviewNavigationCheckpoint = {
      version: CHECKPOINT_VERSION,
      caseId,
      entries: boundedEntries,
      index: boundedIndex,
    }
    window.localStorage.setItem(key, JSON.stringify(checkpoint))
  } catch {
    // 禁用、配额不足或隐私模式下按无检查点继续，不阻塞办理。
  }
}

export function guidedReviewNavigationStepReference(
  action: NavigableAction,
): GuidedReviewNavigationStepReference {
  return {
    actionId: action.id,
    ...(action.pendingItem?.targetId ? { targetId: action.pendingItem.targetId } : {}),
  }
}

export function restoreGuidedReviewNavigation<TAction>(
  caseId: string,
  fallbackAction: TAction | null,
  resolveReference: (reference: GuidedReviewNavigationStepReference) => TAction | null,
): GuidedReviewNavigationState<TAction> {
  const fallback = (): GuidedReviewNavigationState<TAction> => ({
    caseId, entries: fallbackAction ? [fallbackAction] : [], index: 0,
  })
  const checkpoint = readGuidedReviewNavigationCheckpoint(caseId)
  if (!checkpoint) return fallback()
  const restoredEntries = checkpoint.entries.map(resolveReference)
  if (!restoredEntries[checkpoint.index]) return fallback()
  const entries = restoredEntries.filter((action): action is TAction => action !== null)
  const index = restoredEntries.slice(0, checkpoint.index + 1).filter(Boolean).length - 1
  return entries.length > 0 && index >= 0 ? { caseId, entries, index } : fallback()
}
