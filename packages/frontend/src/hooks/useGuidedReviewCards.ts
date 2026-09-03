// 第 10 层：FE_Hooks — 仅在会话中将已有审核事实投影为引导卡片。
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  ArchiveMedium, ArchiveTaskCardSummary, CaseLifecycle, FieldState, InspectionReport, SourceAccessStatus,
} from '@biji/shared/types'
import type { ReviewPendingItem } from './useReviewChecklist'
import { CASE_SUMMARY_CONFIRMATION_FIELD_PATH, REVIEW_SECTION_IDS, REVIEW_TARGET_IDS } from './useReviewChecklist'
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
  | 'waiting'
  | 'ready'

const SESSION_NAVIGATION_ACTION_KINDS: ReadonlySet<GuidedReviewActionKind> = new Set([
  'pending_item',
  'source_recovery',
  'archive_decision',
])

export interface GuidedReviewAction {
  id: string
  kind: GuidedReviewActionKind
  title: string
  description: string
  pendingItem?: ReviewPendingItem
  advanceOnEnter?: boolean
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
  }
}

const GUIDED_HISTORY_REVISIT_TARGETS = new Set<string>([
  ...ENTER_CONFIRM_TARGETS,
  ...DATE_PROMPT_TARGETS,
  REVIEW_TARGET_IDS.evidenceCompleteness,
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
  if (targetId === REVIEW_TARGET_IDS.discNumber || targetId === REVIEW_TARGET_IDS.burningDate) {
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
  return pendingAction({
    id: `handled-${field.targetId || targetId}-${field.label}`,
    sectionId: section.id,
    targetId,
    sectionLabel: section.label,
    fieldLabel,
    reason: '此项此前已处理，可在獬豸助手中核对或修改。',
    severity: 'warning',
    kind: isEvidence ? 'confirmation_required' : 'required_missing',
  })
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
  if (input.photoState === 'error' || input.photoState === 'warning') {
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
  const [selectedActionId, setSelectedActionId] = useState(projection.allActions[0]?.id || '')
  const retainedAction = useRef({
    caseId: input.caseId,
    action: projection.allActions[0] || null as GuidedReviewAction | null,
  })
  const previousCaseId = useRef(input.caseId)
  const projectedSelectedAction = projection.allActions.find(action => action.id === selectedActionId)
  const retainedForCase = retainedAction.current.caseId === input.caseId
    ? retainedAction.current.action : null
  const baseCurrentAction = !projectedSelectedAction
    && retainedForCase?.id === selectedActionId
    && retainedForCase.advanceOnEnter
    && retainedForCase.pendingItem?.kind !== 'confirmation_required'
    ? retainedForCase
    : projectedSelectedAction || projection.allActions[0] || null
  const initialNavigationAction = isSessionNavigationAction(baseCurrentAction) ? baseCurrentAction : null
  const [navigation, setNavigation] = useState(() => ({
    caseId: input.caseId,
    entries: initialNavigationAction ? [initialNavigationAction] : [] as GuidedReviewAction[],
    index: 0,
  }))
  const [revisitedActionId, setRevisitedActionId] = useState<string | null>(null)
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
  useEffect(() => {
    retainedAction.current = { caseId: input.caseId, action: baseCurrentAction }
  }, [baseCurrentAction, input.caseId])

  useEffect(() => {
    setNavigation(previous => {
      const nextNavigationAction = isSessionNavigationAction(baseCurrentAction) ? baseCurrentAction : null
      if (previous.caseId !== input.caseId) return {
        caseId: input.caseId,
        entries: nextNavigationAction ? [nextNavigationAction] : [],
        index: 0,
      }
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
  }, [baseCurrentAction, input.caseId])

  useEffect(() => {
    if (previousCaseId.current !== input.caseId) {
      previousCaseId.current = input.caseId
      setRevisitedActionId(null)
      setSelectedActionId(projection.allActions[0]?.id || '')
    }
  }, [input.caseId, projection.allActions])

  const allActions = useMemo(() => baseCurrentAction?.advanceOnEnter
    && !projection.allActions.some(action => action.id === baseCurrentAction.id)
    ? [baseCurrentAction, ...projection.allActions]
    : projection.allActions, [baseCurrentAction, projection.allActions])
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
    if (!currentAction?.advanceOnEnter) return
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
