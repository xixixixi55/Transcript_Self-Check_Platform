// 第 10 层：FE_Hooks — 仅在会话中将已有审核事实投影为引导卡片。
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  ArchiveMedium, ArchiveTaskCardSummary, CaseLifecycle, InspectionReport, SourceAccessStatus,
} from '@biji/shared/types'
import type { ReviewPendingItem } from './useReviewChecklist'
import { REVIEW_TARGET_IDS } from './useReviewChecklist'

export type GuidedReviewHistoryTone = 'complete' | 'system' | 'warning' | 'recovered'
export type GuidedReviewActionKind =
  | 'pending_item'
  | 'source_recovery'
  | 'lease_recovery'
  | 'save_recovery'
  | 'photo_recovery'
  | 'archive_decision'
  | 'waiting'
  | 'ready'

export interface GuidedReviewHistoryItem {
  id: string
  tone: GuidedReviewHistoryTone
  title: string
  detail?: string
}

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
  pendingItems: ReviewPendingItem[]
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

function archiveMediumLabel(medium: ArchiveMedium | null): string {
  if (medium === 'hard_drive') return '硬盘'
  if (medium === 'optical_disc') return '光盘'
  return '归档介质'
}

function hasCompleteInspectors(report: InspectionReport): boolean {
  const inspectors = report.introduction.inspector_snapshots
    || report.introduction.inspectors.map(item => ({
      name: item.name, unit: item.unit, police_number: item.badge_number,
    }))
  return inspectors.length > 0 && inspectors.every(item =>
    Boolean(item.name?.trim() && item.unit?.trim() && item.police_number?.trim()),
  )
}

function buildFactHistory(input: GuidedReviewProjectionInput): GuidedReviewHistoryItem[] {
  const history: GuidedReviewHistoryItem[] = []
  if (!input.report) return history
  const evidenceCount = input.report.introduction.evidence_list.length
  const recognizedEvidenceCount = input.report.introduction.evidence_list.filter(item =>
    item.material_type_source === 'report' || item.material_type_status === 'confirmed_by_report',
  ).length
  const recognizedFacts = [
    input.report.document_number.trim() ? `文号 ${input.report.document_number.trim()}` : null,
    recognizedEvidenceCount > 0 ? `${recognizedEvidenceCount} 项检材类型` : null,
    input.report.inspection.primary_software?.confirmation_status === 'confirmed_by_report'
      ? `主取证软件 ${input.report.inspection.primary_software.display_name
        || input.report.inspection.primary_software.name}` : null,
  ].filter(Boolean)
  if (recognizedFacts.length > 0) history.push({
    id: 'fact-report-recognition', tone: 'complete', title: '报告内容已自动识别',
    detail: `已从当前报告解析结果整理${recognizedFacts.join('、')}${evidenceCount > recognizedEvidenceCount
      ? `，当前共整理 ${evidenceCount} 项检材` : ''}。`,
  })
  if (input.report.introduction.inspection_place.trim()
    && input.report.inspection.method.trim()
    && input.report.inspection.hardware_device.trim()
    && hasCompleteInspectors(input.report)) history.push({
    id: 'fact-defaults', tone: 'complete', title: '检查设置已沿用',
    detail: '检查人员、地点、方法和硬件设备已从案件信息与默认设置带入。',
  })
  if (evidenceCount > 0 && recognizedEvidenceCount === 0) history.push({
    id: 'fact-evidence', tone: 'complete', title: '检材信息已整理',
    detail: `当前已整理 ${evidenceCount} 项检材信息。`,
  })
  if (input.sourceStatus === 'available' && !input.sourceRequiresReselection) history.push({
    id: 'fact-source', tone: 'complete', title: '报告来源已确认',
    detail: '系统将继续沿用当前案件已授权的报告来源。',
  })
  if (input.saveState === 'failed') history.push({
    id: 'save-problem-failed', tone: 'warning', title: '草稿保存失败',
    detail: '当前输入仍保留在本页面，需要重试保存。',
  })
  if (input.saveState === 'conflict') history.push({
    id: 'save-problem-conflict', tone: 'warning', title: '草稿保存发生冲突',
    detail: '当前输入仍保留在本页面，需要重试或加载服务端版本。',
  })
  if (['read_only', 'expired', 'failed'].includes(input.leaseState)) history.push({
    id: `lease-problem-${input.leaseState}`, tone: 'warning', title: '编辑权限需要恢复',
    detail: input.leaseState === 'read_only'
      ? '当前案件由其他页面占用，本页面暂时只读。'
      : '当前页面没有有效编辑权限，自动保存已经暂停。',
  })
  if (input.photoState === 'error') history.push({
    id: 'photo-problem-error', tone: 'warning', title: '图片保存或读取需要处理',
    detail: '图片尚未完成绑定或当前无法读取，请返回图片控件检查。',
  })
  if (input.photoState === 'warning') history.push({
    id: 'photo-problem-warning', tone: 'warning', title: 'Word 已导出，附件2已省略',
    detail: '当前图片无法完整读取，本次 Word 未生成附件2。',
  })
  if (input.wordExportSucceeded) history.push({
    id: 'word-export-completed', tone: 'complete', title: 'Word 已导出',
    detail: '单独 Word 已生成；这不代表压缩归档或统一导出已经完成。',
  })

  const task = input.archiveTask
  if (input.lifecycle === 'archive_deferred') history.push({
    id: 'archive-deferred', tone: 'complete', title: '草稿已保存并稍后处理',
    detail: '当前草稿已安全保留，可以继续审核、返回案件列表或稍后开始压缩。',
  })
  if (input.lifecycle === 'archive_interrupted') history.push({
    id: 'archive-interrupted', tone: 'warning', title: '上次压缩未完成',
    detail: '草稿仍然可用，可重新开始或继续稍后处理。',
  })
  if (task && ['archive_queued', 'archiving'].includes(input.lifecycle)) history.push({
    id: `archive-stage-${task.stage}`, tone: 'system',
    title: '后台归档处理中', detail: backgroundArchiveDetail(task),
  })
  if (['archive_verified', 'exported'].includes(input.lifecycle)) history.push({
    id: 'archive-completed', tone: 'complete', title: '后台归档已完成校验',
    detail: input.pendingItems.some(item => item.targetId === REVIEW_TARGET_IDS.discNumber)
      ? `压缩产物已完成校验，仍需整理${archiveMediumLabel(input.archiveMedium)}编号后再统一导出。`
      : `压缩产物已完成校验，${archiveMediumLabel(input.archiveMedium)}信息已整理。`,
  })
  if (input.lifecycle === 'exported') history.push({
    id: 'export-completed', tone: 'complete', title: '统一导出已完成',
    detail: 'Word 与现有归档产物已按统一导出流程生成；案件信息继续修改后可重新导出。',
  })
  return history
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

export function deriveGuidedReviewProjection(input: GuidedReviewProjectionInput): GuidedReviewProjection {
  if (!input.report) return {
    history: [], pendingItems: [], allActions: [], systemStatus: null, readyToGenerate: false,
  }
  const pendingItems = input.pendingItems.filter(item => !SYSTEM_OUTPUT_TARGETS.has(item.targetId))
  const allActions: GuidedReviewAction[] = []
  if (input.leaseState !== 'editable' && input.leaseState !== 'acquiring') {
    allActions.push({ id: 'lease-recovery', kind: 'lease_recovery', title: '请恢复编辑权限', description: '当前页面不能写入案件，请先恢复有效编辑租约。' })
  }
  if (input.saveHasPending && ['saving', 'failed', 'conflict'].includes(input.saveState)) {
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
  allActions.push(...pendingItems.map(pendingAction))
  if (['review_ready', 'archive_deferred', 'archive_interrupted'].includes(input.lifecycle)
    && !input.sourceRequiresReselection) {
    allActions.push({
      id: 'archive-decision', kind: 'archive_decision', title: '请选择压缩时机',
      description: input.lifecycle === 'archive_deferred'
        ? '当前已选择稍后处理，也可以现在开始压缩。'
        : '建议现在开始压缩；也可以保留案件并稍后处理。',
    })
  }
  const systemStatus = buildSystemStatus(input)
  const readyToGenerate = pendingItems.length === 0
    && ['archive_verified', 'exported'].includes(input.lifecycle)
    && input.archiveParts !== null
  if (allActions.length === 0) allActions.push(readyToGenerate
    ? { id: 'ready', kind: 'ready', title: '请确认并生成笔录', description: '笔录已准备完成，生成时仍由现有保存与导出门控进行最终检查。' }
    : { id: 'waiting', kind: 'waiting', title: systemStatus ? `请稍候，${systemStatus.title}` : '请稍候，正在整理下一步', description: systemStatus?.detail || '当前没有需要立即填写的事项。' })
  return { history: buildFactHistory(input), pendingItems, allActions, systemStatus, readyToGenerate }
}

export function useGuidedReviewCards(input: GuidedReviewProjectionInput) {
  const projection = deriveGuidedReviewProjection(input)
  const historySignature = projection.history.map(item => item.id).join('|')
  const [history, setHistory] = useState(projection.history)
  const [historyCaseId, setHistoryCaseId] = useState(input.caseId)
  const [selectedActionId, setSelectedActionId] = useState(projection.allActions[0]?.id || '')
  const [previousAction, setPreviousAction] = useState<GuidedReviewAction | null>(null)
  const [revisitedAction, setRevisitedAction] = useState<GuidedReviewAction | null>(null)
  const retainedAction = useRef({
    caseId: input.caseId,
    action: projection.allActions[0] || null as GuidedReviewAction | null,
  })
  const previousPending = useRef(new Map(projection.pendingItems.map(item => [item.id, item])))
  const previousPendingCaseId = useRef(input.caseId)
  const previousRecoveryState = useRef({
    caseId: input.caseId,
    saveState: input.saveState,
    leaseState: input.leaseState,
    photoState: input.photoState,
  })
  const pendingSignature = projection.pendingItems.map(item => item.id).join('|')
  const projectedSelectedAction = projection.allActions.find(action => action.id === selectedActionId)
  const retainedForCase = retainedAction.current.caseId === input.caseId
    ? retainedAction.current.action : null
  const baseCurrentAction = !projectedSelectedAction
    && retainedForCase?.id === selectedActionId
    && retainedForCase.advanceOnEnter
    ? retainedForCase
    : projectedSelectedAction || projection.allActions[0] || null
  const currentAction = revisitedAction || baseCurrentAction
  const previousBaseAction = useRef({ caseId: input.caseId, action: baseCurrentAction })
  const selectedPendingId = currentAction?.advanceOnEnter ? currentAction.pendingItem?.id : undefined
  const appendCompletedHistory = useCallback((items: ReviewPendingItem[]) => {
    if (!items.length) return
    setHistory(current => {
      const known = new Set(current.map(item => item.id))
      const additions = items.filter(item => !known.has(`completed-${item.id}`)).map(item => ({
        id: `completed-${item.id}`, tone: 'complete' as const, title: `${item.fieldLabel}已完成`,
        detail: '当前案件事实已不再要求处理此事项。',
      }))
      return additions.length ? [...current, ...additions] : current
    })
  }, [])

  useEffect(() => {
    retainedAction.current = { caseId: input.caseId, action: baseCurrentAction }
  }, [baseCurrentAction, input.caseId])

  useEffect(() => {
    const previous = previousBaseAction.current
    if (previous.caseId !== input.caseId) {
      previousBaseAction.current = { caseId: input.caseId, action: baseCurrentAction }
      setPreviousAction(null)
      setRevisitedAction(null)
      return
    }
    if (previous.action?.kind === 'pending_item'
      && previous.action.id !== baseCurrentAction?.id
      && !projection.allActions.some(action => action.id === previous.action?.id)) {
      setPreviousAction(previous.action)
    }
    previousBaseAction.current = { caseId: input.caseId, action: baseCurrentAction }
  }, [baseCurrentAction, input.caseId, projection.allActions])

  useEffect(() => {
    if (historyCaseId !== input.caseId) {
      setHistoryCaseId(input.caseId)
      setHistory(projection.history)
      setSelectedActionId(projection.allActions[0]?.id || '')
      setPreviousAction(null)
      setRevisitedAction(null)
      return
    }
    setHistory(current => {
      const known = new Set(current.map(item => item.id))
      const additions = projection.history.filter(item => !known.has(item.id))
      if (known.has('archive-interrupted')
        && projection.history.some(item => item.id.startsWith('archive-stage-') || item.id === 'archive-completed')
        && !known.has('archive-recovered')) additions.push({
        id: 'archive-recovered', tone: 'recovered', title: '压缩办理已恢复',
        detail: '上次未完成状态已经处理，当前案件已继续进入现有归档流程。',
      })
      return additions.length ? [...current, ...additions] : current
    })
  }, [historyCaseId, historySignature, input.caseId])

  useEffect(() => {
    const nextPending = new Map(projection.pendingItems.map(item => [item.id, item]))
    if (previousPendingCaseId.current !== input.caseId) {
      previousPendingCaseId.current = input.caseId
      previousPending.current = nextPending
      return
    }
    const completed = [...previousPending.current.values()].filter(item => !nextPending.has(item.id))
    appendCompletedHistory(completed.filter(item => item.id !== selectedPendingId))
    previousPending.current = nextPending
  }, [appendCompletedHistory, input.caseId, pendingSignature, selectedPendingId])

  useEffect(() => {
    const previous = previousRecoveryState.current
    if (previous.caseId !== input.caseId) {
      previousRecoveryState.current = {
        caseId: input.caseId,
        saveState: input.saveState,
        leaseState: input.leaseState,
        photoState: input.photoState,
      }
      return
    }
    const additions: GuidedReviewHistoryItem[] = []
    if (['failed', 'conflict'].includes(previous.saveState)
      && ['idle', 'saved', 'not_changed'].includes(input.saveState)) additions.push({
      id: 'save-recovered', tone: 'recovered', title: '草稿保存状态已恢复',
      detail: '此前保留在页面中的输入已经重新进入正常保存流程。',
    })
    if (['read_only', 'expired', 'failed'].includes(previous.leaseState)
      && input.leaseState === 'editable') additions.push({
      id: 'lease-recovered', tone: 'recovered', title: '编辑权限已恢复',
      detail: '当前页面已经可以继续编辑并保存案件。',
    })
    if (['error', 'warning'].includes(previous.photoState) && input.photoState === 'ready') additions.push({
      id: 'photo-recovered', tone: 'recovered', title: '附件2图片状态已恢复',
      detail: '图片已经重新进入可保存和完整导出的状态。',
    })
    if (additions.length) setHistory(current => {
      const known = new Set(current.map(item => item.id))
      const novel = additions.filter(item => !known.has(item.id))
      return novel.length ? [...current, ...novel] : current
    })
    previousRecoveryState.current = {
      caseId: input.caseId,
      saveState: input.saveState === 'saving' && ['failed', 'conflict'].includes(previous.saveState)
        ? previous.saveState : input.saveState,
      leaseState: input.leaseState === 'acquiring' && ['read_only', 'expired', 'failed'].includes(previous.leaseState)
        ? previous.leaseState : input.leaseState,
      photoState: input.photoState === 'uploading' && ['error', 'warning'].includes(previous.photoState)
        ? previous.photoState : input.photoState,
    }
  }, [input.caseId, input.leaseState, input.photoState, input.saveState])

  const allActions = useMemo(() => baseCurrentAction?.advanceOnEnter
    && !projection.allActions.some(action => action.id === baseCurrentAction.id)
    ? [baseCurrentAction, ...projection.allActions]
    : projection.allActions, [baseCurrentAction, projection.allActions])
  const finalizeRetainedAction = useCallback(() => {
    if (!currentAction?.advanceOnEnter) return
    if (projection.allActions.some(action => action.id === currentAction.id)) return
    if (currentAction.pendingItem) appendCompletedHistory([currentAction.pendingItem])
  }, [appendCompletedHistory, currentAction, projection.allActions])
  const selectAction = useCallback((actionId: string) => {
    const action = allActions.find(candidate => candidate.id === actionId)
    if (!action) return
    if (action.id !== currentAction?.id) {
      if (currentAction?.kind === 'pending_item') setPreviousAction(currentAction)
      finalizeRetainedAction()
    }
    setRevisitedAction(null)
    setSelectedActionId(action.id)
  }, [allActions, currentAction?.id, finalizeRetainedAction])
  const confirmCurrentAction = useCallback(() => {
    if (!currentAction?.advanceOnEnter) return
    if (revisitedAction) {
      setRevisitedAction(null)
      setSelectedActionId(projection.allActions[0]?.id || '')
      return
    }
    if (projection.allActions.some(action => action.id === currentAction.id)) return
    finalizeRetainedAction()
    setSelectedActionId(projection.allActions[0]?.id || '')
  }, [currentAction, finalizeRetainedAction, projection.allActions, revisitedAction])

  const returnToPreviousAction = useCallback(() => {
    if (previousAction) setRevisitedAction(previousAction)
  }, [previousAction])
  const returnToCurrentAction = useCallback(() => setRevisitedAction(null), [])

  return {
    ...projection, allActions, history, currentAction, previousAction,
    isReviewingPrevious: Boolean(revisitedAction), selectAction, confirmCurrentAction,
    returnToPreviousAction, returnToCurrentAction,
  }
}
