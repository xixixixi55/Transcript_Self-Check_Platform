// Layer 10: FE_Hooks — session-only projection of existing review facts into guided cards.
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
  photoState: 'ready' | 'uploading' | 'error'
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
  md5: '正在生成文件校验值',
  manifest: '正在整理归档清单',
  completed: '归档处理已完成',
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
  return facts.length ? facts.join('，') : '后台任务仍在运行，可继续处理其他待办。'
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
  if (input.report.document_number.trim()) history.push({
    id: 'fact-document-number', tone: 'complete', title: '文书信息已整理',
    detail: `已沿用文号 ${input.report.document_number.trim()}。`,
  })
  if (input.report.introduction.inspection_place.trim()
    && input.report.inspection.method.trim()
    && input.report.inspection.hardware_device.trim()
    && hasCompleteInspectors(input.report)) history.push({
    id: 'fact-defaults', tone: 'complete', title: '检查设置已沿用',
    detail: '检查人员、地点、方法和硬件设备已从案件信息与默认设置带入。',
  })
  const evidenceCount = input.report.introduction.evidence_list.length
  if (evidenceCount > 0) history.push({
    id: 'fact-evidence', tone: 'complete', title: '检材信息已整理',
    detail: `当前已整理 ${evidenceCount} 项检材信息。`,
  })
  if (input.sourceStatus === 'available' && !input.sourceRequiresReselection) history.push({
    id: 'fact-source', tone: 'complete', title: '报告来源已确认',
    detail: '系统将继续沿用当前案件已授权的报告来源。',
  })

  const task = input.archiveTask
  if (input.lifecycle === 'archive_deferred') history.push({
    id: 'archive-deferred', tone: 'warning', title: '已选择稍后压缩',
    detail: '案件与草稿已保留，可随时继续开始压缩。',
  })
  if (input.lifecycle === 'archive_interrupted') history.push({
    id: 'archive-interrupted', tone: 'warning', title: '上次压缩未完成',
    detail: '草稿仍然可用，可重新开始或继续稍后处理。',
  })
  if (task && ['archive_queued', 'archiving'].includes(input.lifecycle)) history.push({
    id: `archive-stage-${task.stage}`, tone: 'system',
    title: ARCHIVE_STAGE_LABELS[task.stage] || '后台归档正在处理', detail: archiveDetail(task),
  })
  if (['archive_verified', 'exported'].includes(input.lifecycle)) history.push({
    id: 'archive-completed', tone: 'complete', title: '归档处理已完成',
    detail: input.archiveMedium === 'hard_drive'
      ? '压缩产物已完成校验，并按硬盘介质办理。'
      : '压缩产物已完成校验，并按光盘介质办理。',
  })
  if (input.lifecycle === 'exported') history.push({
    id: 'export-completed', tone: 'complete', title: '案件材料已完成导出',
    detail: '如案件信息继续修改，可使用现有导出入口重新生成。',
  })
  return history
}

function buildSystemStatus(input: GuidedReviewProjectionInput): GuidedReviewSystemStatus | null {
  if (input.photoState === 'uploading') return { title: '正在保存图片', detail: '图片上传和绑定完成后会自动沿用。' }
  if (input.sourceStatus === 'pending') return { title: '正在复核报告来源', detail: '系统完成快速复核后会更新可办理事项。' }
  if (input.archiveTask && ['archive_queued', 'archiving'].includes(input.lifecycle)) return {
    title: ARCHIVE_STAGE_LABELS[input.archiveTask.stage] || '后台归档正在处理',
    detail: archiveDetail(input.archiveTask),
  }
  return null
}

function pendingAction(item: ReviewPendingItem): GuidedReviewAction {
  return {
    id: `pending-${item.id}`, kind: 'pending_item', pendingItem: item,
    title: `处理${item.fieldLabel}`, description: item.reason,
  }
}

export function deriveGuidedReviewProjection(input: GuidedReviewProjectionInput): GuidedReviewProjection {
  if (!input.report) return {
    history: [], pendingItems: [], allActions: [], systemStatus: null, readyToGenerate: false,
  }
  const pendingItems = input.pendingItems.filter(item => !SYSTEM_OUTPUT_TARGETS.has(item.targetId))
  const allActions: GuidedReviewAction[] = []
  if (input.sourceRequiresReselection || ['invalid', 'requires_reselection'].includes(input.sourceStatus)) {
    allActions.push({ id: 'source-recovery', kind: 'source_recovery', title: '重新选择报告来源', description: '当前来源不可用，请重新选择后继续。' })
  }
  if (input.leaseState !== 'editable' && input.leaseState !== 'acquiring') {
    allActions.push({ id: 'lease-recovery', kind: 'lease_recovery', title: '恢复编辑权限', description: '当前页面不能写入案件，请先恢复有效编辑租约。' })
  }
  if (input.photoState === 'error') {
    allActions.push({ id: 'photo-recovery', kind: 'photo_recovery', title: '处理图片保存问题', description: '图片尚未完成绑定，请使用现有图片控件检查并重试。' })
  }
  allActions.push(...pendingItems.map(pendingAction))
  if (['review_ready', 'archive_deferred', 'archive_interrupted'].includes(input.lifecycle)
    && !input.sourceRequiresReselection) {
    allActions.push({
      id: 'archive-decision', kind: 'archive_decision', title: '选择压缩时机',
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
    ? { id: 'ready', kind: 'ready', title: '笔录已准备完成', description: '生成时仍由现有保存与导出门控进行最终检查。' }
    : { id: 'waiting', kind: 'waiting', title: systemStatus?.title || '等待下一步办理', description: systemStatus?.detail || '当前没有需要立即填写的事项。' })
  return { history: buildFactHistory(input), pendingItems, allActions, systemStatus, readyToGenerate }
}

export function useGuidedReviewCards(input: GuidedReviewProjectionInput) {
  const projection = deriveGuidedReviewProjection(input)
  const historySignature = projection.history.map(item => item.id).join('|')
  const [history, setHistory] = useState(projection.history)
  const [historyCaseId, setHistoryCaseId] = useState(input.caseId)
  const [selectedActionId, setSelectedActionId] = useState(projection.allActions[0]?.id || '')
  const previousPending = useRef(new Map(projection.pendingItems.map(item => [item.id, item])))
  const previousPendingCaseId = useRef(input.caseId)
  const pendingSignature = projection.pendingItems.map(item => item.id).join('|')

  useEffect(() => {
    if (historyCaseId !== input.caseId) {
      setHistoryCaseId(input.caseId)
      setHistory(projection.history)
      setSelectedActionId(projection.allActions[0]?.id || '')
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
    if (completed.length) setHistory(current => {
      const known = new Set(current.map(item => item.id))
      const additions = completed.filter(item => !known.has(`completed-${item.id}`)).map(item => ({
        id: `completed-${item.id}`, tone: 'complete' as const, title: `${item.fieldLabel}已完成`,
        detail: '当前案件事实已不再要求处理此事项。',
      }))
      return additions.length ? [...current, ...additions] : current
    })
    previousPending.current = nextPending
  }, [input.caseId, pendingSignature])

  const currentAction = useMemo(
    () => projection.allActions.find(action => action.id === selectedActionId) || projection.allActions[0] || null,
    [projection.allActions, selectedActionId],
  )
  const selectAction = useCallback((actionId: string) => setSelectedActionId(actionId), [])

  return { ...projection, history, currentAction, selectAction }
}
