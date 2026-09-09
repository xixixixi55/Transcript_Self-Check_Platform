// 第 10 层：FE_Hooks — 仅在会话中将已有审核事实投影为引导卡片。
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  ArchiveMedium, ArchiveTaskCardSummary, CaseLifecycle, FieldState, InspectionReport, SourceAccessStatus,
} from '@biji/shared/types'
import type { ReviewPendingItem } from './useReviewChecklist'
import { CASE_SUMMARY_CONFIRMATION_FIELD_PATH, REVIEW_SECTION_IDS, REVIEW_TARGET_IDS } from './useReviewChecklist'
import {
  guidedReviewNavigationStepReference,
  restoreGuidedReviewNavigation,
  writeGuidedReviewNavigationCheckpoint,
  type GuidedReviewNavigationState,
  type GuidedReviewNavigationStepReference,
} from './useGuidedReviewNavigationPersistence'
import {
  buildReportHistory,
  type GuidedReviewHistoryField,
  type GuidedReviewHistoryItem,
} from './useGuidedReviewHistoryProjection'

export type {
  GuidedReviewHistoryField,
  GuidedReviewHistoryItem,
  GuidedReviewHistoryMaterial,
  GuidedReviewHistoryTone,
} from './useGuidedReviewHistoryProjection'

export type GuidedReviewActionKind =
  | 'pending_item'
  | 'source_recovery'
  | 'lease_recovery'
  | 'save_recovery'
  | 'photo_recovery'
  | 'archive_decision'
  | 'archive_deferred'
  | 'waiting'
  | 'ready'

const SESSION_NAVIGATION_ACTION_KINDS: ReadonlySet<GuidedReviewActionKind> = new Set([
  'pending_item',
  'source_recovery',
  'archive_decision',
  'archive_deferred',
])

export interface GuidedReviewAction {
  id: string
  kind: GuidedReviewActionKind
  title: string
  description: string
  pendingItem?: ReviewPendingItem
  advanceOnEnter?: boolean
  requiresExplicitAdvance?: boolean
}

export interface GuidedReviewSystemStatus {
  title: string
  detail: string
}

export interface GuidedReviewProjectionInput {
  caseId: string
  report: InspectionReport | null
  fieldStates?: Record<string, FieldState>
  pendingItems: ReviewPendingItem[]
  caseSummaryReviewed?: boolean
  lifecycle: CaseLifecycle
  archiveTask?: ArchiveTaskCardSummary | null
  archiveMedium: ArchiveMedium | null
  archiveParts: { disc_number?: string | null; size_bytes?: number | null }[] | null
  sourceStatus: SourceAccessStatus
  sourceRequiresReselection: boolean
  leaseState: 'editable' | 'read_only' | 'expired' | 'failed' | 'acquiring'
  saveState: 'idle' | 'saving' | 'saved' | 'failed' | 'conflict' | 'not_changed'
  saveHasPending: boolean
  photoState: 'ready' | 'uploading' | 'error' | 'warning'
  wordExportSucceeded: boolean
}

export interface GuidedReviewProjection {
  history: GuidedReviewHistoryItem[]
  previouslyHandledFields: GuidedReviewHistoryField[]
  pendingItems: ReviewPendingItem[]
  allActions: GuidedReviewAction[]
  systemStatus: GuidedReviewSystemStatus | null
  readyToGenerate: boolean
}

const SYSTEM_OUTPUT_TARGETS = new Set([
  REVIEW_TARGET_IDS.result('rar_filename'),
  REVIEW_TARGET_IDS.result('md5_hash'),
  REVIEW_TARGET_IDS.result('file_size'),
])

const ARCHIVE_STAGE_LABELS: Record<string, string> = {
  queued: '归档任务正在等待处理',
  inventory: '正在整理待归档内容',
  preflight_verified: '归档前检查已完成',
  winrar: '正在生成压缩分卷',
  integrity: '正在校验压缩文件',
  integrity_verified: '压缩文件完整性已确认',
  hash: '正在生成文件校验值',
  manifest: '正在整理归档清单',
  completed: '归档产物已生成，正在确认结果',
}

function formatBytes(bytes: number | null): string | null {
  if (!bytes || bytes < 1) return null
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB 已生成`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB 已生成`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB 已生成`
}

function archiveDetail(task: ArchiveTaskCardSummary): string {
  const facts = [
    formatBytes(task.output_bytes),
    task.output_volume_count ? `已检测到 ${task.output_volume_count} 个分卷` : null,
  ].filter(Boolean)
  return facts.length ? facts.join('，') : '后台任务正在推进'
}

function backgroundArchiveDetail(task: ArchiveTaskCardSummary): string {
  const stage = ARCHIVE_STAGE_LABELS[task.stage] || '后台任务正在推进'
  return `${stage}；${archiveDetail(task)}。可继续处理其他待办。`
}

function buildFactHistory(input: GuidedReviewProjectionInput): GuidedReviewHistoryItem[] {
  return buildReportHistory(input.report, input.fieldStates)
}

function buildPersistedHandledFields(
  report: InspectionReport,
  fieldStates?: Record<string, FieldState>,
): GuidedReviewHistoryField[] {
  const completeness = fieldStates?.['introduction.evidence_list.completeness']
  const fields: GuidedReviewHistoryField[] = completeness?.source === 'user'
    && completeness.confirmation === 'confirmed' ? [{
    label: '检材完整性', value: '已确认', userProvided: true,
    targetId: REVIEW_TARGET_IDS.evidenceCompleteness,
  }] : []
  const summaryConfirmation = fieldStates?.[CASE_SUMMARY_CONFIRMATION_FIELD_PATH]
  const summaryWasEdited = fieldStates?.['introduction.case_summary']?.source === 'user'
  if (summaryConfirmation?.source === 'user' && summaryConfirmation.confirmation === 'confirmed'
    && report.introduction.case_summary.trim() && !summaryWasEdited) {
    fields.push({
      label: '案件简要情况', value: report.introduction.case_summary.trim(), userProvided: true,
      targetId: REVIEW_TARGET_IDS.caseSummary,
    })
  }
  const photoCount = report.attachments?.photo_ids?.length || 0
  if (photoCount > 0) {
    fields.push({
      label: '检材照片', value: `已上传 ${photoCount} 张图片`, userProvided: true,
      targetId: REVIEW_TARGET_IDS.photos,
    })
  }
  return fields
}

function isSessionNavigationAction(action: GuidedReviewAction | null): action is GuidedReviewAction {
  return Boolean(action && SESSION_NAVIGATION_ACTION_KINDS.has(action.kind))
}

function buildSystemStatus(input: GuidedReviewProjectionInput): GuidedReviewSystemStatus | null {
  if (input.saveHasPending && input.saveState === 'saving') return {
    title: '正在保存当前输入', detail: '保存完成前，当前输入会继续保留在本页面。',
  }
  if (input.photoState === 'uploading') return { title: '正在保存图片', detail: '图片上传和绑定完成后会自动沿用。' }
  if (input.sourceStatus === 'pending') return { title: '正在复核报告来源', detail: '系统完成快速复核后会更新可办理事项。' }
  if (input.archiveTask && ['archive_queued', 'archiving'].includes(input.lifecycle)) return {
    title: '后台归档处理中',
    detail: backgroundArchiveDetail(input.archiveTask),
  }
  return null
}

const DATE_PROMPT_TARGETS = new Set<string>([
  REVIEW_TARGET_IDS.entrustTime,
  REVIEW_TARGET_IDS.inspectionTimeRange,
  REVIEW_TARGET_IDS.burningDate,
])

const ENTER_CONFIRM_TARGETS = new Set<string>([
  REVIEW_TARGET_IDS.documentNumber,
  REVIEW_TARGET_IDS.evidenceCompleteness,
  REVIEW_TARGET_IDS.entrustUnit,
  REVIEW_TARGET_IDS.entrustPersons,
  REVIEW_TARGET_IDS.caseSummary,
  REVIEW_TARGET_IDS.inspectionRequirement,
  REVIEW_TARGET_IDS.inspectionPlace,
  REVIEW_TARGET_IDS.inspectionMethod,
  REVIEW_TARGET_IDS.hardwareDevice,
  REVIEW_TARGET_IDS.primarySoftwareName,
  REVIEW_TARGET_IDS.primarySoftwareVersion,
  REVIEW_TARGET_IDS.discNumber,
  REVIEW_TARGET_IDS.result('evidence_number'),
  REVIEW_TARGET_IDS.result('data_summary'),
  REVIEW_TARGET_IDS.result('rar_filename'),
  REVIEW_TARGET_IDS.result('md5_hash'),
  REVIEW_TARGET_IDS.result('file_size'),
])

function pendingPrompt(item: ReviewPendingItem): string {
  if (item.targetId === REVIEW_TARGET_IDS.photos) return '请上传检材照片'
  if (item.kind === 'confirmation_required') return `请确认${item.fieldLabel}`
  if (item.kind === 'validation') return `请检查并修正${item.fieldLabel}`
  if (DATE_PROMPT_TARGETS.has(item.targetId)) return `请选择${item.fieldLabel}`
  return `请输入${item.fieldLabel}`
}

function pendingAction(item: ReviewPendingItem): GuidedReviewAction {
  return {
    id: `pending-${item.id}`, kind: 'pending_item', pendingItem: item,
    title: pendingPrompt(item), description: item.reason,
    advanceOnEnter: ENTER_CONFIRM_TARGETS.has(item.targetId),
    requiresExplicitAdvance: item.targetId === REVIEW_TARGET_IDS.photos
      || item.targetId === REVIEW_TARGET_IDS.entrustTime,
  }
}

const GUIDED_HISTORY_REVISIT_TARGETS = new Set<string>([
  ...ENTER_CONFIRM_TARGETS,
  ...DATE_PROMPT_TARGETS,
  REVIEW_TARGET_IDS.evidenceCompleteness,
  REVIEW_TARGET_IDS.photos,
])

function resolvedHistoryTarget(targetId: string | undefined): string | null {
  if (!targetId) return null
  if (/^review-target-evidence-\d+$/.test(targetId)) return REVIEW_TARGET_IDS.evidenceCompleteness
  if (SYSTEM_OUTPUT_TARGETS.has(targetId)) return null
  return GUIDED_HISTORY_REVISIT_TARGETS.has(targetId) ? targetId : null
}

export function canRevisitGuidedHistoryField(field: GuidedReviewHistoryField): boolean {
  return resolvedHistoryTarget(field.targetId) !== null
}

function historySection(targetId: string): { id: string; label: string } {
  if (targetId === REVIEW_TARGET_IDS.documentNumber) {
    return { id: REVIEW_SECTION_IDS.document, label: '文书信息' }
  }
  if (targetId === REVIEW_TARGET_IDS.discNumber
    || targetId === REVIEW_TARGET_IDS.burningDate
    || targetId === REVIEW_TARGET_IDS.photos) {
    return { id: REVIEW_SECTION_IDS.attachments, label: '附件' }
  }
  if (targetId.startsWith('review-target-result-')) {
    return { id: REVIEW_SECTION_IDS.inspection, label: '二、检查' }
  }
  return { id: REVIEW_SECTION_IDS.introduction, label: '一、绪论' }
}

function handledHistoryAction(field: GuidedReviewHistoryField): GuidedReviewAction | null {
  const targetId = resolvedHistoryTarget(field.targetId)
  if (!targetId) return null
  const isEvidence = targetId === REVIEW_TARGET_IDS.evidenceCompleteness
  const fieldLabel = isEvidence ? '检材完整性' : field.label
  const section = historySection(targetId)
  const action = pendingAction({
    id: `handled-${field.targetId || targetId}-${field.label}`,
    sectionId: section.id,
    targetId,
    sectionLabel: section.label,
    fieldLabel,
    reason: '此项此前已处理，可在獬豸助手中核对或修改。',
    severity: 'warning',
    kind: isEvidence ? 'confirmation_required' : 'required_missing',
  })
  return targetId === REVIEW_TARGET_IDS.photos ? {
    ...action,
    title: '请核对检材照片',
    description: `${field.value}，可继续检查、删除或重新上传。`,
  } : action
}

function actionForStoredReference(reference: GuidedReviewNavigationStepReference,
  projection: GuidedReviewProjection,
): GuidedReviewAction | null {
  const projectedAction = projection.allActions.find(action => (
    action.id === reference.actionId
    || (reference.targetId && action.pendingItem?.targetId === reference.targetId)
  ))
  if (isSessionNavigationAction(projectedAction || null)) return projectedAction || null
  if (!reference.targetId) return null
  const handledField = [...projection.previouslyHandledFields,
    ...projection.history.flatMap(item => item.fields || [])]
    .find(field => field.userProvided && canRevisitGuidedHistoryField(field)
      && field.targetId === reference.targetId)
  return handledField ? handledHistoryAction(handledField) : null
}

function persistedNavigation(caseId: string, projection: GuidedReviewProjection,
): GuidedReviewNavigationState<GuidedReviewAction> {
  const projectedFirstAction = projection.allActions[0] || null
  const firstAction = isSessionNavigationAction(projectedFirstAction) ? projectedFirstAction : null
  return restoreGuidedReviewNavigation(
    caseId,
    firstAction,
    reference => actionForStoredReference(reference, projection),
  )
}

const CASE_SUMMARY_REVIEW_ITEM: ReviewPendingItem = {
  id: 'review-section-introduction-案件简要情况',
  sectionId: 'review-section-introduction',
  targetId: REVIEW_TARGET_IDS.caseSummary,
  sectionLabel: '一、绪论',
  fieldLabel: '案件简要情况',
  reason: '报告已自动整理案件简要情况，请人工核对并按需修改。',
  severity: 'warning',
  kind: 'confirmation_required',
}

const CASE_SUMMARY_PRECEDING_TARGETS = new Set<string>([
  REVIEW_TARGET_IDS.documentNumber,
  REVIEW_TARGET_IDS.entrustUnit,
  REVIEW_TARGET_IDS.entrustPersons,
  REVIEW_TARGET_IDS.entrustTime,
])

export function deriveGuidedReviewProjection(input: GuidedReviewProjectionInput): GuidedReviewProjection {
  if (!input.report) return {
    history: [], previouslyHandledFields: [], pendingItems: [], allActions: [],
    systemStatus: null, readyToGenerate: false,
  }
  const pendingItems = input.pendingItems.filter(item => !SYSTEM_OUTPUT_TARGETS.has(item.targetId))
  if (input.caseSummaryReviewed === false
    && !pendingItems.some(item => item.targetId === REVIEW_TARGET_IDS.caseSummary)) {
    const nextIntroductionFieldIndex = pendingItems.findIndex(
      item => !CASE_SUMMARY_PRECEDING_TARGETS.has(item.targetId),
    )
    pendingItems.splice(
      nextIntroductionFieldIndex === -1 ? pendingItems.length : nextIntroductionFieldIndex,
      0,
      CASE_SUMMARY_REVIEW_ITEM,
    )
  }
  const allActions: GuidedReviewAction[] = []
  const hasPhotoPending = pendingItems.some(item => item.targetId === REVIEW_TARGET_IDS.photos)
  if (input.leaseState !== 'editable' && input.leaseState !== 'acquiring') {
    allActions.push({ id: 'lease-recovery', kind: 'lease_recovery', title: '请恢复编辑权限', description: '当前页面不能写入案件，请先恢复有效编辑租约。' })
  }
  if (input.saveHasPending && ['failed', 'conflict'].includes(input.saveState)) {
    allActions.push({
      id: 'save-recovery', kind: 'save_recovery', title: '请恢复草稿保存',
      description: input.saveState === 'saving'
        ? '正在重新保存，完成前当前输入会继续保留。'
        : '当前输入仍保留在本页面，请先恢复保存后继续。',
    })
  }
  if (input.sourceRequiresReselection || ['invalid', 'requires_reselection'].includes(input.sourceStatus)) {
    allActions.push({ id: 'source-recovery', kind: 'source_recovery', title: '请重新选择报告来源', description: '当前来源不可用，请重新选择后继续。' })
  }
  if ((input.photoState === 'error' || input.photoState === 'warning') && !hasPhotoPending) {
    allActions.push({
      id: 'photo-recovery', kind: 'photo_recovery',
      title: input.photoState === 'warning' ? '请检查附件2图片' : '请处理图片保存问题',
      description: input.photoState === 'warning'
        ? 'Word 已导出，但附件2未生成；可返回图片控件检查后重新导出。'
        : '图片尚未完成绑定，请使用现有图片控件检查并重试。',
    })
  }
  const archiveDecisionAction: GuidedReviewAction = {
      id: 'archive-decision', kind: 'archive_decision', title: '请选择压缩时机',
      description: input.lifecycle === 'archive_deferred'
        ? '当前已选择稍后处理，也可以现在开始压缩。'
        : '建议现在开始压缩；也可以保留案件并稍后处理。',
  }
  const canChooseArchiveTiming = ['review_ready', 'archive_deferred', 'archive_interrupted'].includes(input.lifecycle)
    && !input.sourceRequiresReselection
  if (canChooseArchiveTiming && input.lifecycle !== 'archive_deferred') {
    allActions.push(archiveDecisionAction)
  }
  const prioritizedPendingItems = [...pendingItems].sort((left, right) => (
    Number(right.targetId === REVIEW_TARGET_IDS.discNumber)
      - Number(left.targetId === REVIEW_TARGET_IDS.discNumber)
  ))
  allActions.push(...prioritizedPendingItems.map(pendingAction))
  if (canChooseArchiveTiming && input.lifecycle === 'archive_deferred') {
    if (allActions.length === 0) allActions.push({
      id: 'archive-deferred', kind: 'archive_deferred', title: '草稿已保存',
      description: '压缩已设为稍后处理。当前没有待填写事项，稍后可从案件工作台继续。',
    })
    allActions.push(archiveDecisionAction)
  }
  const systemStatus = buildSystemStatus(input)
  const readyToGenerate = pendingItems.length === 0
    && ['archive_verified', 'exported'].includes(input.lifecycle)
    && input.archiveParts !== null
  if (allActions.length === 0) allActions.push(readyToGenerate
    ? { id: 'ready', kind: 'ready', title: '当前审核已完成', description: '请保存并退出；返回案件工作台后可统一导出。' }
    : { id: 'waiting', kind: 'waiting', title: systemStatus ? `请稍候，${systemStatus.title}` : '请稍候，正在整理下一步', description: systemStatus?.detail || '当前没有需要立即填写的事项。' })
  return {
    history: buildFactHistory(input),
    previouslyHandledFields: buildPersistedHandledFields(input.report, input.fieldStates),
    pendingItems, allActions, systemStatus, readyToGenerate,
  }
}

export function useGuidedReviewCards(input: GuidedReviewProjectionInput) {
  const projection = deriveGuidedReviewProjection(input)
  const [initialNavigation] = useState<GuidedReviewNavigationState<GuidedReviewAction>>(() => (
    input.report ? persistedNavigation(input.caseId, projection) : {
      caseId: input.caseId, entries: [], index: 0,
    }
  ))
  const initialCurrentAction = initialNavigation.entries[initialNavigation.index]
    || projection.allActions[0] || null
  const [selectedActionId, setSelectedActionId] = useState(initialCurrentAction?.id || '')
  const retainedAction = useRef({
    caseId: input.caseId,
    action: initialCurrentAction as GuidedReviewAction | null,
  })
  const previousLifecycle = useRef(input.lifecycle)
  const projectedSelectedAction = projection.allActions.find(action => action.id === selectedActionId)
  const leaseRecoveryAction = projection.allActions.find(action => action.kind === 'lease_recovery')
  const retainedForCase = retainedAction.current.caseId === input.caseId
    ? retainedAction.current.action : null
  const selectedOrFallbackAction = !projectedSelectedAction
    && retainedForCase?.id === selectedActionId
    && (retainedForCase.advanceOnEnter || retainedForCase.requiresExplicitAdvance)
    && retainedForCase.pendingItem?.kind !== 'confirmation_required'
    ? retainedForCase
    : projectedSelectedAction || projection.allActions[0] || null
  const baseCurrentAction = leaseRecoveryAction || selectedOrFallbackAction
  const [navigation, setNavigation] = useState<GuidedReviewNavigationState<GuidedReviewAction>>(initialNavigation)
  const [revisitedActionId, setRevisitedActionId] = useState<string | null>(() => (
    initialCurrentAction && !projection.allActions.some(action => action.id === initialCurrentAction.id)
      ? initialCurrentAction.id : null
  ))
  const hydratedCaseIdRef = useRef<string | null>(input.report ? input.caseId : null)
  const skipNavigationAppendRef = useRef<string | null>(input.report ? input.caseId : null)
  const skipSelectedFallbackRef = useRef<string | null>(null)
  const skipCheckpointWriteRef = useRef<string | null>(null)
  const terminalSaveTransitionRef = useRef(false)
  const navigationAction = navigation.entries[navigation.index] || null
  const revisitedNavigationAction = navigationAction?.id === revisitedActionId
    ? navigationAction : null
  const currentIsTransientAction = Boolean(
    baseCurrentAction
      && !isSessionNavigationAction(baseCurrentAction)
      && (navigation.entries.length === 0 || navigation.index === navigation.entries.length - 1),
  )
  const currentAction = revisitedNavigationAction
    || (currentIsTransientAction ? baseCurrentAction : navigationAction || baseCurrentAction)
  const waitingForTerminalSave = navigationAction?.pendingItem?.kind === 'confirmation_required'
    && projection.allActions[0]?.kind === 'archive_decision'
  const shouldHoldTerminalTransition = () => {
    if (!waitingForTerminalSave) return false
    if (input.saveState === 'saving') terminalSaveTransitionRef.current = true
    return !terminalSaveTransitionRef.current || input.saveHasPending
      || ['saving', 'failed', 'conflict'].includes(input.saveState)
  }

  useEffect(() => {
    if (!input.report || hydratedCaseIdRef.current === input.caseId) return
    const restored = persistedNavigation(input.caseId, projection)
    const restoredCurrent = restored.entries[restored.index] || projection.allActions[0] || null
    hydratedCaseIdRef.current = input.caseId
    skipNavigationAppendRef.current = input.caseId
    skipSelectedFallbackRef.current = input.caseId
    skipCheckpointWriteRef.current = input.caseId
    retainedAction.current = { caseId: input.caseId, action: restoredCurrent }
    setNavigation(restored)
    setSelectedActionId(restoredCurrent?.id || '')
    setRevisitedActionId(restoredCurrent
      && !projection.allActions.some(action => action.id === restoredCurrent.id)
      ? restoredCurrent.id : null)
  }, [input.caseId, input.report, projection])

  useEffect(() => {
    retainedAction.current = { caseId: input.caseId, action: baseCurrentAction }
  }, [baseCurrentAction, input.caseId])

  useEffect(() => {
    if (skipSelectedFallbackRef.current === input.caseId) {
      skipSelectedFallbackRef.current = null
      return
    }
    const fallbackAction = projection.allActions[0]
    if (shouldHoldTerminalTransition()) return
    const fallbackActionId = fallbackAction?.id
    if (!projectedSelectedAction && baseCurrentAction?.id === fallbackActionId
      && selectedActionId !== fallbackActionId) {
      setSelectedActionId(fallbackActionId || '')
    }
  }, [baseCurrentAction?.id, input.caseId, input.saveHasPending, input.saveState,
    projectedSelectedAction, projection.allActions, selectedActionId, waitingForTerminalSave])

  useEffect(() => {
    const enteredDeferred = previousLifecycle.current !== 'archive_deferred'
      && input.lifecycle === 'archive_deferred'
    previousLifecycle.current = input.lifecycle
    if (!enteredDeferred || selectedActionId !== 'archive-decision') return
    const nextAction = projection.allActions.find(action => action.id !== 'archive-decision')
    setRevisitedActionId(null)
    setSelectedActionId(nextAction?.id || '')
  }, [input.lifecycle, projection.allActions, selectedActionId])

  useEffect(() => {
    if (!input.report || hydratedCaseIdRef.current !== input.caseId) return
    if (skipNavigationAppendRef.current === input.caseId) {
      skipNavigationAppendRef.current = null
      return
    }
    if (shouldHoldTerminalTransition()) return
    if (waitingForTerminalSave) terminalSaveTransitionRef.current = false
    setNavigation(previous => {
      const nextNavigationAction = isSessionNavigationAction(baseCurrentAction) ? baseCurrentAction : null
      if (previous.caseId !== input.caseId) return previous
      if (!nextNavigationAction) return previous
      const latestIndex = previous.entries.length - 1
      if (previous.entries[latestIndex]?.id === nextNavigationAction.id) return previous
      const entries = [...previous.entries, nextNavigationAction]
      return {
        ...previous,
        entries,
        index: previous.index === latestIndex ? entries.length - 1 : previous.index,
      }
    })
  }, [baseCurrentAction, input.caseId, input.report, input.saveHasPending, input.saveState,
    waitingForTerminalSave])

  useEffect(() => {
    if (!input.report || hydratedCaseIdRef.current !== input.caseId
      || navigation.caseId !== input.caseId) return
    if (skipCheckpointWriteRef.current === input.caseId) {
      skipCheckpointWriteRef.current = null
      return
    }
    writeGuidedReviewNavigationCheckpoint(
      input.caseId,
      navigation.entries.map(guidedReviewNavigationStepReference),
      navigation.index,
    )
  }, [input.caseId, input.report, navigation])

  const allActions = useMemo(() => {
    const projectedActions = baseCurrentAction?.pendingItem?.targetId === REVIEW_TARGET_IDS.photos
      ? projection.allActions.filter(action => action.kind !== 'photo_recovery')
      : projection.allActions
    return (baseCurrentAction?.advanceOnEnter || baseCurrentAction?.requiresExplicitAdvance)
      && !projectedActions.some(action => action.id === baseCurrentAction.id)
      ? [baseCurrentAction, ...projectedActions]
      : projectedActions
  }, [baseCurrentAction, projection.allActions])
  const selectAction = useCallback((actionId: string) => {
    const action = allActions.find(candidate => candidate.id === actionId)
    if (!action) return
    setRevisitedActionId(null)
    setNavigation(previous => {
      if (!isSessionNavigationAction(action)) return {
        ...previous,
        index: Math.max(0, previous.entries.length - 1),
      }
      if (previous.entries[previous.index]?.id === action.id) return previous
      const entries = [...previous.entries.slice(0, previous.index + 1), action]
      return { ...previous, entries, index: entries.length - 1 }
    })
    setSelectedActionId(action.id)
  }, [allActions])
  const confirmCurrentAction = useCallback(() => {
    if (!currentAction?.advanceOnEnter && !currentAction?.requiresExplicitAdvance) return
    if (navigation.index < navigation.entries.length - 1) {
      setNavigation(previous => ({ ...previous, index: Math.min(previous.index + 1, previous.entries.length - 1) }))
      return
    }
    if (projection.allActions.some(action => action.id === currentAction.id)) return
    setSelectedActionId(projection.allActions[0]?.id || '')
  }, [currentAction, navigation.entries.length, navigation.index, projection.allActions])

  const returnToPreviousAction = useCallback(() => {
    setNavigation(previous => ({ ...previous, index: Math.max(0, previous.index - 1) }))
  }, [])
  const returnToNextAction = useCallback(() => {
    setNavigation(previous => ({
      ...previous,
      index: Math.min(previous.entries.length - 1, previous.index + 1),
    }))
  }, [])
  const revisitAction = useCallback((action: GuidedReviewAction) => {
    setRevisitedActionId(action.id)
    setNavigation(previous => {
      let existingIndex = -1
      for (let index = previous.entries.length - 1; index >= 0; index -= 1) {
        if (previous.entries[index].id === action.id) {
          existingIndex = index
          break
        }
      }
      if (existingIndex >= 0) return { ...previous, index: existingIndex }
      const entries = [
        ...previous.entries.slice(0, previous.index),
        action,
        ...previous.entries.slice(previous.index),
      ]
      return { ...previous, entries, index: previous.index }
    })
  }, [])
  const revisitHandledField = useCallback((field: GuidedReviewHistoryField) => {
    const action = handledHistoryAction(field)
    if (action) revisitAction(action)
  }, [revisitAction])
  const previousAction = !currentIsTransientAction && navigation.index > 0
    ? navigation.entries[navigation.index - 1] : null
  const canReturnToPrevious = !currentIsTransientAction && navigation.index > 0
  const canReturnToNext = !currentIsTransientAction && navigation.index < navigation.entries.length - 1

  return {
    ...projection, allActions, currentAction, previousAction,
    isReviewingPrevious: canReturnToNext, canReturnToPrevious, canReturnToNext,
    selectAction, confirmCurrentAction, revisitAction, revisitHandledField,
    returnToPreviousAction, returnToNextAction,
  }
}
