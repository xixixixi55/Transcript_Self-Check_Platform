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
import {
  buildGuidedReviewSystemStatus,
  type GuidedReviewSystemStatus,
} from './useGuidedReviewSystemStatus'

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

export type { GuidedReviewSystemStatus } from './useGuidedReviewSystemStatus'

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
  if (/^review-target-(?:inspector|software-tool|process-step)-\d+$/.test(targetId)) return targetId
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

const OPEN_USER_WORK_ACTION_KINDS: ReadonlySet<GuidedReviewActionKind> = new Set([
  'pending_item',
  'source_recovery',
  'lease_recovery',
  'save_recovery',
  'photo_recovery',
])

const MANUAL_STEP_ORDER = new Map<string, number>([
  [REVIEW_TARGET_IDS.documentNumber, 10],
  [REVIEW_TARGET_IDS.entrustUnit, 20],
  [REVIEW_TARGET_IDS.entrustPersons, 30],
  [REVIEW_TARGET_IDS.entrustTime, 40],
  [REVIEW_TARGET_IDS.caseSummary, 50],
  [REVIEW_TARGET_IDS.inspectionRequirement, 60],
  [REVIEW_TARGET_IDS.inspectionTimeRange, 70],
  [REVIEW_TARGET_IDS.inspectionPlace, 80],
  [REVIEW_TARGET_IDS.evidenceCompleteness, 90],
  [REVIEW_TARGET_IDS.inspectionMethod, 120],
  [REVIEW_TARGET_IDS.hardwareDevice, 130],
  [REVIEW_TARGET_IDS.primarySoftwareName, 150],
  [REVIEW_TARGET_IDS.primarySoftwareVersion, 160],
  [REVIEW_TARGET_IDS.result('data_summary'), 180],
  [REVIEW_TARGET_IDS.photos, 900],
  [REVIEW_TARGET_IDS.discNumber, 910],
  [REVIEW_TARGET_IDS.burningDate, 920],
])

function manualStepOrder(action: GuidedReviewAction): number {
  const targetId = action.pendingItem?.targetId || ''
  if (/^review-target-inspector-\d+$/.test(targetId)) return 100
  if (/^review-target-software-tool-\d+$/.test(targetId)) return 140
  return MANUAL_STEP_ORDER.get(targetId) ?? 500
}

function hasOpenUserWork(projection: GuidedReviewProjection): boolean {
  return projection.allActions.some(action => OPEN_USER_WORK_ACTION_KINDS.has(action.kind))
}

function completedManualActions(projection: GuidedReviewProjection): GuidedReviewAction[] {
  const seenTargets = new Set<string>()
  return [
    ...projection.history.flatMap(item => item.fields || []),
    ...projection.previouslyHandledFields,
  ].flatMap(field => {
    const isDocumentNumber = field.targetId === REVIEW_TARGET_IDS.documentNumber
    if ((!field.userProvided && !isDocumentNumber) || !canRevisitGuidedHistoryField(field)) return []
    const action = handledHistoryAction(field)
    const targetId = action?.pendingItem?.targetId
    if (!action || !targetId || seenTargets.has(targetId)) return []
    seenTargets.add(targetId)
    return [action]
  }).sort((left, right) => manualStepOrder(left) - manualStepOrder(right))
}

function completedReentryIndex(actions: GuidedReviewAction[]): number {
  const documentNumberIndex = actions.findIndex(
    action => action.pendingItem?.targetId === REVIEW_TARGET_IDS.documentNumber,
  )
  return documentNumberIndex >= 0 ? documentNumberIndex : Math.max(0, actions.length - 1)
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
  const restored = restoreGuidedReviewNavigation(
    caseId,
    firstAction,
    reference => actionForStoredReference(reference, projection),
  )
  if (hasOpenUserWork(projection)) return restored
  const completedActions = completedManualActions(projection)
  return completedActions.length > 0 ? {
    caseId, entries: completedActions, index: completedReentryIndex(completedActions),
  } : restored
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
  if (['failed', 'conflict'].includes(input.saveState)) {
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
        ? '附件2图片读取异常；请返回图片控件检查，完成保存后再到案件工作台重新导出。'
        : '图片尚未完成绑定，请使用现有图片控件检查并重试。',
    })
  }
  const archiveDecisionAction: GuidedReviewAction = {
      id: 'archive-decision', kind: 'archive_decision', title: '请选择压缩时机',
      description: input.lifecycle === 'archive_deferred'
        ? '当前已选择稍后处理，也可以现在开始压缩。'
        : '建议现在开始压缩；也可以保留案件并稍后处理。',
  }
  const sourceBlocksArchive = input.sourceRequiresReselection
    || ['invalid', 'requires_reselection'].includes(input.sourceStatus)
  const canChooseArchiveTiming = ['review_ready', 'archive_deferred', 'archive_interrupted'].includes(input.lifecycle)
    && !sourceBlocksArchive
  if (canChooseArchiveTiming && input.lifecycle !== 'archive_deferred') {
    allActions.push(archiveDecisionAction)
  }
  allActions.push(...pendingItems.map(pendingAction))
  if (canChooseArchiveTiming && input.lifecycle === 'archive_deferred') {
    if (allActions.length === 0) {
      if (input.saveHasPending || input.saveState === 'saving') allActions.push({
        id: 'waiting-for-deferred-save', kind: 'waiting', title: '请稍候，正在保存当前输入',
        description: '保存完成后，才会确认草稿已保存并可返回案件工作台。',
      })
      else allActions.push({
        id: 'archive-deferred', kind: 'archive_deferred', title: '草稿已保存',
        description: '压缩已设为稍后处理。当前没有待填写事项，稍后可从案件工作台继续。',
      })
    }
    allActions.push(archiveDecisionAction)
  }
  const systemStatus = buildGuidedReviewSystemStatus(input)
  const readyToGenerate = pendingItems.length === 0 && allActions.length === 0
  if (allActions.length === 0) allActions.push(readyToGenerate
    ? { id: 'ready', kind: 'ready', title: '当前审核已完成', description: '请保存并退出；返回案件工作台后可完成导出。' }
    : { id: 'waiting', kind: 'waiting', title: systemStatus ? `请稍候，${systemStatus.title}` : '请稍候，正在整理下一步', description: systemStatus?.detail || '当前没有需要立即填写的事项。' })
  return {
    history: buildFactHistory(input),
    previouslyHandledFields: buildPersistedHandledFields(input.report, input.fieldStates),
    pendingItems, allActions, systemStatus, readyToGenerate,
  }
}

export function useGuidedReviewCards(input: GuidedReviewProjectionInput) {
  const projection = deriveGuidedReviewProjection(input)
  const terminalNavigationMode = !hasOpenUserWork(projection)
  const completedReentryCaseIdRef = useRef<string | null>(
    input.report && terminalNavigationMode ? input.caseId : null,
  )
  const isCompletedReentryNavigation = completedReentryCaseIdRef.current === input.caseId
    && terminalNavigationMode
  const completedActions = terminalNavigationMode ? completedManualActions(projection) : []
  const completedActionIds = completedActions.map(action => action.id).join('\u0000')
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
  const selectedNavigationAction = navigation.entries.find(action => action.id === selectedActionId)
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
  const terminalEndpointAction = terminalNavigationMode
    ? projection.allActions[0] || null : null
  const terminalBaseAction = terminalEndpointAction && baseCurrentAction
    && projection.allActions.some(action => action.id === baseCurrentAction.id)
    ? baseCurrentAction : null
  const currentIsTransientAction = Boolean(
    baseCurrentAction
      && !isSessionNavigationAction(baseCurrentAction)
      && !(isCompletedReentryNavigation && selectedNavigationAction)
      && (navigation.entries.length === 0 || navigation.index === navigation.entries.length - 1),
  )
  const showingTerminalAction = Boolean(
    terminalBaseAction
      && selectedActionId === terminalBaseAction.id
      && !revisitedNavigationAction
      && (navigation.entries.length === 0 || navigation.index === navigation.entries.length - 1),
  )
  const currentAction = revisitedNavigationAction
    || (showingTerminalAction || currentIsTransientAction
      ? baseCurrentAction : navigationAction || baseCurrentAction)
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
    completedReentryCaseIdRef.current = terminalNavigationMode ? input.caseId : null
    skipNavigationAppendRef.current = input.caseId
    skipSelectedFallbackRef.current = input.caseId
    skipCheckpointWriteRef.current = input.caseId
    retainedAction.current = { caseId: input.caseId, action: restoredCurrent }
    setNavigation(restored)
    setSelectedActionId(restoredCurrent?.id || '')
    setRevisitedActionId(restoredCurrent
      && !projection.allActions.some(action => action.id === restoredCurrent.id)
      ? restoredCurrent.id : null)
  }, [input.caseId, input.report, projection, terminalNavigationMode])

  useEffect(() => {
    if (!terminalNavigationMode && completedReentryCaseIdRef.current === input.caseId) {
      completedReentryCaseIdRef.current = null
    }
  }, [input.caseId, terminalNavigationMode])

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
    if (!projectedSelectedAction && !(isCompletedReentryNavigation && selectedNavigationAction)
      && baseCurrentAction?.id === fallbackActionId
      && selectedActionId !== fallbackActionId) {
      setSelectedActionId(fallbackActionId || '')
    }
  }, [baseCurrentAction?.id, input.caseId, input.saveHasPending, input.saveState,
    projectedSelectedAction, projection.allActions, selectedActionId,
    isCompletedReentryNavigation, selectedNavigationAction, waitingForTerminalSave])

  useEffect(() => {
    const enteredDeferred = previousLifecycle.current !== 'archive_deferred'
      && input.lifecycle === 'archive_deferred'
    previousLifecycle.current = input.lifecycle
    if (!enteredDeferred || selectedActionId !== 'archive-decision') return
    const nextAction = projection.allActions.find(action => action.id !== 'archive-decision')
    setRevisitedActionId(null)
    setSelectedActionId(nextAction?.id || '')
  }, [input.lifecycle, projection.allActions, selectedActionId])

  const archiveDecisionAvailable = projection.allActions.some(action => action.kind === 'archive_decision')
  useEffect(() => {
    if (archiveDecisionAvailable) return
    setNavigation(previous => {
      const retainedEntries = previous.entries.filter(action => action.kind !== 'archive_decision')
      if (retainedEntries.length === previous.entries.length) return previous
      const retainedThroughCurrent = previous.entries.slice(0, previous.index + 1)
        .filter(action => action.kind !== 'archive_decision').length
      return {
        ...previous,
        entries: retainedEntries,
        index: Math.max(0, Math.min(retainedEntries.length - 1, retainedThroughCurrent - 1)),
      }
    })
  }, [archiveDecisionAvailable])

  useEffect(() => {
    if (!input.report || hydratedCaseIdRef.current !== input.caseId) return
    if (skipNavigationAppendRef.current === input.caseId) {
      skipNavigationAppendRef.current = null
      return
    }
    if (shouldHoldTerminalTransition()) return
    if (waitingForTerminalSave) terminalSaveTransitionRef.current = false
    setNavigation(previous => {
      const nextNavigationAction = terminalBaseAction
        ? null : isSessionNavigationAction(baseCurrentAction) ? baseCurrentAction : null
      if (previous.caseId !== input.caseId) return previous
      if (!nextNavigationAction) return previous
      const latestIndex = previous.entries.length - 1
      if (previous.index !== latestIndex) return previous
      if (previous.entries[latestIndex]?.id === nextNavigationAction.id) return previous
      const entries = [...previous.entries, nextNavigationAction]
      return {
        ...previous,
        entries,
        index: previous.index === latestIndex ? entries.length - 1 : previous.index,
      }
    })
  }, [baseCurrentAction, input.caseId, input.report, input.saveHasPending, input.saveState,
    terminalBaseAction, waitingForTerminalSave])

  useEffect(() => {
    if (!input.report || !terminalNavigationMode || !terminalBaseAction
      || completedActions.length === 0) return
    setNavigation(previous => {
      if (previous.caseId !== input.caseId) return previous
      const previousIds = previous.entries.map(action => action.id).join('\u0000')
      if (previousIds === completedActionIds) return previous
      return { ...previous, entries: completedActions, index: completedActions.length - 1 }
    })
  }, [completedActionIds, input.caseId, input.report, terminalBaseAction, terminalNavigationMode])

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
      const nextIndex = Math.min(navigation.index + 1, navigation.entries.length - 1)
      setSelectedActionId(navigation.entries[nextIndex]?.id || '')
      setNavigation(previous => ({ ...previous, index: Math.min(previous.index + 1, previous.entries.length - 1) }))
      return
    }
    if (projection.allActions.some(action => action.id === currentAction.id)) return
    setRevisitedActionId(null)
    setSelectedActionId(projection.allActions[0]?.id || '')
  }, [currentAction, navigation.entries.length, navigation.index, projection.allActions])

  const returnToPreviousAction = useCallback(() => {
    if (showingTerminalAction && navigationAction) {
      setRevisitedActionId(navigationAction.id)
      setSelectedActionId(navigationAction.id)
      return
    }
    const previousIndex = Math.max(0, navigation.index - 1)
    setSelectedActionId(navigation.entries[previousIndex]?.id || '')
    setNavigation(previous => ({ ...previous, index: Math.max(0, previous.index - 1) }))
  }, [navigation.entries, navigation.index, navigationAction, showingTerminalAction])
  const returnToNextAction = useCallback(() => {
    if (navigation.index >= navigation.entries.length - 1 && terminalEndpointAction) {
      setRevisitedActionId(null)
      setSelectedActionId(terminalEndpointAction.id)
      return
    }
    const nextIndex = Math.min(navigation.entries.length - 1, navigation.index + 1)
    setSelectedActionId(navigation.entries[nextIndex]?.id || '')
    setNavigation(previous => ({
      ...previous,
      index: Math.min(previous.entries.length - 1, previous.index + 1),
    }))
  }, [navigation.entries, navigation.index, terminalEndpointAction])
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
  const showingNavigationAction = Boolean(
    revisitedNavigationAction || (!showingTerminalAction && !currentIsTransientAction && navigationAction),
  )
  const previousAction = showingTerminalAction
    ? navigationAction
    : showingNavigationAction && navigation.index > 0
      ? navigation.entries[navigation.index - 1] : null
  const canReturnToPrevious = showingTerminalAction
    ? Boolean(navigationAction)
    : showingNavigationAction && navigation.index > 0
  const canReturnToNext = showingNavigationAction && (
    navigation.index < navigation.entries.length - 1 || Boolean(terminalEndpointAction)
  )

  return {
    ...projection, allActions, currentAction, previousAction,
    isReviewingPrevious: canReturnToNext, canReturnToPrevious, canReturnToNext,
    selectAction, confirmCurrentAction, revisitAction, revisitHandledField,
    returnToPreviousAction, returnToNextAction,
  }
}
