import { act, renderHook } from '@testing-library/react'
import type { ArchiveTaskCardSummary, InspectionReport } from '@biji/shared/types'
import { describe, expect, it } from 'vitest'
import { getReviewPendingItems, REVIEW_TARGET_IDS } from './useReviewChecklist'
import type { GuidedReviewProjectionInput } from './useGuidedReviewCards'
import { deriveGuidedReviewProjection, useGuidedReviewCards } from './useGuidedReviewCards'

const syntheticReport: InspectionReport = {
  title: '电子数据检查笔录',
  document_number: 'SYN-TEST〔2026〕001号',
  case_number: 'SYNTHETIC-CASE-001',
  introduction: {
    entrust_unit: 'SYNTHETIC-UNIT',
    entrust_persons: ['SYNTHETIC-PERSON'],
    entrust_time: '2026年08月25日',
    case_summary: 'SYNTHETIC CASE SUMMARY',
    evidence_list: [{
      id: 'SYNTHETIC-EVIDENCE-1', device_type: '手机', evidence_number: 'SYNTHETIC-E-001',
      material_type: 'phone', material_type_status: 'confirmed_by_report', material_type_source: 'report',
      imei1: 'SYNTHETIC-IMEI', extractable: true,
    }],
    inspection_requirement: 'SYNTHETIC REQUIREMENT',
    inspection_time_range: '2026年08月25日09时00分至2026年08月25日10时00分',
    inspectors: [],
    inspector_snapshots: [{
      name: 'SYNTHETIC-INSPECTOR', unit: 'SYNTHETIC-UNIT', position: 'TEST', police_number: 'SYNTHETIC-BADGE',
    }],
    inspection_place: 'SYNTHETIC-PLACE',
  },
  inspection: {
    method: 'SYNTHETIC-METHOD', hardware_device: 'SYNTHETIC-HARDWARE', software_tools: [], process_steps: [],
    primary_software: {
      name: 'SYNTHETIC-SOFTWARE', version: '1.0', display_name: 'SYNTHETIC-SOFTWARE 1.0',
      confirmation_status: 'confirmed_by_report', provenance: [], candidates: [],
    },
    result: {
      evidence_number: 'SYNTHETIC-E-001', software_name: 'SYNTHETIC-SOFTWARE', software_version: '1.0',
      data_summary: 'SYNTHETIC DATA', rar_filename: '', md5_hash: '', file_size: '',
    },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: ['SYNTHETIC-PHOTO-1', 'SYNTHETIC-PHOTO-2'], disc_number: '' },
}

const archiveTask: ArchiveTaskCardSummary = {
  task_id: 'SYNTHETIC-TASK', case_id: 'SYNTHETIC-CASE-001', status: 'running',
  progress_kind: 'workflow_milestone', stage: 'winrar', stage_label: '正在生成压缩分卷',
  stage_index: 4, stage_count: 9, percent: 30, updated_at: '2026-08-25T01:00:00Z',
  last_heartbeat_at: null, output_bytes: 2048, output_volume_count: 1,
  last_output_change_at: null, worker_state: 'owned_running', started_at: '2026-08-25T00:59:00Z',
  finished_at: null, error_summary: null, allowed_actions: [],
}

function buildInput(report = syntheticReport): GuidedReviewProjectionInput {
  return {
    caseId: 'SYNTHETIC-CASE-001', report,
    pendingItems: getReviewPendingItems(report, undefined, null, {
      'introduction.evidence_list.completeness': {
        field_path: 'introduction.evidence_list.completeness', source: 'user', confirmation: 'confirmed',
        revision: 1, last_changed_at: '2026-08-25T01:00:00Z',
      },
    }),
    lifecycle: 'archiving' as const,
    archiveTask,
    archiveMedium: null,
    archiveParts: null,
    sourceStatus: 'available' as const,
    sourceRequiresReselection: false,
    saveState: 'saved' as const,
    saveHasPending: false,
    leaseState: 'editable' as const,
    photoState: 'ready' as const,
    wordExportSucceeded: false,
  }
}

describe('guided review projection', () => {
  it('classifies existing facts without re-asking complete defaults or system-produced archive fields', () => {
    const projection = deriveGuidedReviewProjection(buildInput())

    expect(projection.pendingItems.some(item => item.targetId.includes('inspector'))).toBe(false)
    expect(projection.pendingItems.some(item => [
      REVIEW_TARGET_IDS.result('rar_filename'),
      REVIEW_TARGET_IDS.result('md5_hash'),
      REVIEW_TARGET_IDS.result('file_size'),
    ].includes(item.targetId))).toBe(false)
    expect(projection.systemStatus).toEqual(expect.objectContaining({
      title: '后台归档处理中', detail: expect.stringContaining('正在生成压缩分卷'),
    }))
    expect(projection.history).toContainEqual(expect.objectContaining({
      id: 'fact-report-recognition',
      title: '报告内容已自动识别',
      detail: expect.stringContaining('SYN-TEST〔2026〕001号'),
    }))
    expect(projection.history.map(item => `${item.title}${item.detail || ''}`).join(' ')).not.toMatch(
      /SYNTHETIC-TASK|revision|Worker|worker|令牌|token|[A-Z]:\\/,
    )
  })

  it('rebuilds refresh history from current facts and does not retain stale intermediate stages', () => {
    const running = deriveGuidedReviewProjection(buildInput())
    const completed = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_verified',
      archiveTask: { ...archiveTask, status: 'succeeded', stage: 'completed', stage_label: '归档完成' },
      archiveMedium: 'optical_disc', archiveParts: [{ disc_number: 'GP20260825-01', size_bytes: 2048 }],
    })

    expect(running.history.some(item => item.id === 'archive-stage-winrar')).toBe(true)
    expect(completed.history.some(item => item.id === 'archive-stage-winrar')).toBe(false)
    expect(completed.history.some(item => item.title === '后台归档已完成校验')).toBe(true)
  })

  it('keeps the current action stable when a background fact adds a higher-priority item', () => {
    const initial = buildInput({ ...syntheticReport, document_number: '' })
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: initial },
    })
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('文号')
    expect(result.current.currentAction?.title).toBe('请输入文号')

    const sourceInvalid = {
      ...initial, sourceStatus: 'requires_reselection' as const, sourceRequiresReselection: true,
    }
    rerender({ input: sourceInvalid })
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('文号')
    expect(result.current.allActions.some(action => action.kind === 'source_recovery')).toBe(true)

    const saveFailed = {
      ...sourceInvalid, saveState: 'failed' as const, saveHasPending: true,
    }
    rerender({ input: saveFailed })
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('文号')
    expect(result.current.allActions).toContainEqual(expect.objectContaining({
      id: 'save-recovery', kind: 'save_recovery', title: '请恢复草稿保存',
    }))

    act(() => result.current.selectAction('source-recovery'))
    expect(result.current.currentAction?.kind).toBe('source_recovery')
    expect(result.current.previousAction?.pendingItem?.fieldLabel).toBe('文号')

    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('文号')
    expect(result.current.isReviewingPrevious).toBe(true)

    act(() => result.current.returnToCurrentAction())
    expect(result.current.currentAction?.kind).toBe('source_recovery')

    rerender({ input: buildInput() })
    expect(result.current.history.some(item => item.title === '文号已完成')).toBe(true)
  })

  it('keeps a completed text action current until Enter confirms it', () => {
    const initial = buildInput({ ...syntheticReport, document_number: '' })
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: initial },
    })
    const documentActionId = result.current.currentAction?.id

    rerender({ input: buildInput({ ...syntheticReport, document_number: 'S' }) })

    expect(result.current.currentAction?.id).toBe(documentActionId)
    expect(result.current.allActions.some(action => action.id === documentActionId)).toBe(true)
    expect(result.current.history.some(item => item.title === '文号已完成')).toBe(false)

    act(() => result.current.confirmCurrentAction())

    expect(result.current.currentAction?.id).not.toBe(documentActionId)
    expect(result.current.allActions.some(action => action.id === documentActionId)).toBe(false)
    expect(result.current.history.some(item => item.title === '文号已完成')).toBe(true)
  })

  it('returns to the prior pending field after switching to the photo action', () => {
    const report = {
      ...syntheticReport,
      document_number: '',
      attachments: { ...syntheticReport.attachments, photo_ids: [] },
    }
    const { result } = renderHook(() => useGuidedReviewCards(buildInput(report)))
    const photoAction = result.current.allActions.find(
      action => action.pendingItem?.targetId === REVIEW_TARGET_IDS.photos,
    )
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('文号')
    expect(photoAction).toBeTruthy()

    act(() => result.current.selectAction(photoAction!.id))
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('检材照片')
    expect(result.current.previousAction?.pendingItem?.fieldLabel).toBe('文号')

    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('文号')
  })

  it('keeps the previous completed action available for session-only step navigation', () => {
    const initial = buildInput({ ...syntheticReport, document_number: '' })
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: initial },
    })
    const documentActionId = result.current.currentAction?.id

    rerender({ input: buildInput({ ...syntheticReport, document_number: 'SYN-TEST〔2026〕009号' }) })
    act(() => result.current.confirmCurrentAction())

    const nextActionId = result.current.currentAction?.id
    expect(nextActionId).not.toBe(documentActionId)
    expect(result.current.previousAction?.id).toBe(documentActionId)

    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.id).toBe(documentActionId)
    expect(result.current.isReviewingPrevious).toBe(true)
    expect(result.current.allActions.some(action => action.id === documentActionId)).toBe(false)

    act(() => result.current.returnToCurrentAction())
    expect(result.current.currentAction?.id).toBe(nextActionId)
    expect(result.current.isReviewingPrevious).toBe(false)
  })

  it('phrases every current action as an explicit assistant prompt', () => {
    const pendingItems = [
      {
        id: 'SYNTHETIC-DOCUMENT', sectionId: 'review-section-document',
        targetId: REVIEW_TARGET_IDS.documentNumber, sectionLabel: '文书信息', fieldLabel: '文号',
        reason: '当前必填字段为空。', severity: 'warning' as const, kind: 'required_missing' as const,
      },
      {
        id: 'SYNTHETIC-ENTRUST-TIME', sectionId: 'review-section-introduction',
        targetId: REVIEW_TARGET_IDS.entrustTime, sectionLabel: '一、绪论', fieldLabel: '委托时间',
        reason: '当前必填字段为空。', severity: 'warning' as const, kind: 'required_missing' as const,
      },
      {
        id: 'SYNTHETIC-EVIDENCE-CONFIRMATION', sectionId: 'review-section-introduction',
        targetId: REVIEW_TARGET_IDS.evidenceCompleteness, sectionLabel: '一、绪论', fieldLabel: '检材完整性',
        reason: '请确认检材是否完整。', severity: 'error' as const, kind: 'confirmation_required' as const,
      },
    ]
    const pending = deriveGuidedReviewProjection({ ...buildInput(), pendingItems })
    expect(pending.allActions.map(action => action.title)).toEqual([
      '请输入文号', '请选择委托时间', '请确认检材完整性',
    ])

    const decision = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems: [], lifecycle: 'review_ready', archiveTask: null,
    })
    expect(decision.allActions[0]?.title).toBe('请选择压缩时机')

    const waiting = deriveGuidedReviewProjection({ ...buildInput(), pendingItems: [] })
    expect(waiting.allActions[0]?.title).toBe('请稍候，后台归档处理中')

    const ready = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems: [], lifecycle: 'archive_verified',
      archiveParts: [{ disc_number: 'GP20260825-01', size_bytes: 2048 }],
    })
    expect(ready.allActions[0]?.title).toBe('请确认并生成笔录')
  })

  it('projects save conflicts and lease failures as recoverable actions and records recovery', () => {
    const failed: GuidedReviewProjectionInput = {
      ...buildInput(), saveState: 'conflict' as const, saveHasPending: true,
      leaseState: 'expired' as const,
    }
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: failed },
    })

    expect(result.current.allActions.slice(0, 2)).toEqual([
      expect.objectContaining({ id: 'lease-recovery', kind: 'lease_recovery' }),
      expect.objectContaining({ id: 'save-recovery', kind: 'save_recovery' }),
    ])
    expect(result.current.history).toEqual(expect.arrayContaining([
      expect.objectContaining({ title: '草稿保存发生冲突', tone: 'warning' }),
      expect.objectContaining({ title: '编辑权限需要恢复', tone: 'warning' }),
    ]))

    rerender({ input: { ...buildInput(), saveState: 'saved', saveHasPending: false } })
    expect(result.current.history).toEqual(expect.arrayContaining([
      expect.objectContaining({ title: '草稿保存状态已恢复', tone: 'recovered' }),
      expect.objectContaining({ title: '编辑权限已恢复', tone: 'recovered' }),
    ]))
    expect(result.current.allActions.some(action => ['save_recovery', 'lease_recovery'].includes(action.kind))).toBe(false)
  })

  it('projects an omitted attachment2 as a recoverable image action and records a fact-based recovery', () => {
    const warning: GuidedReviewProjectionInput = { ...buildInput(), photoState: 'warning' }
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: warning },
    })

    expect(result.current.allActions).toContainEqual(expect.objectContaining({
      id: 'photo-recovery', kind: 'photo_recovery', title: '请检查附件2图片',
    }))
    expect(result.current.history).toContainEqual(expect.objectContaining({
      id: 'photo-problem-warning', tone: 'warning', title: 'Word 已导出，附件2已省略',
    }))

    rerender({ input: buildInput() })
    expect(result.current.history).toContainEqual(expect.objectContaining({
      id: 'photo-recovered', tone: 'recovered', title: '附件2图片状态已恢复',
    }))
    expect(result.current.allActions.some(action => action.kind === 'photo_recovery')).toBe(false)
  })

  it('keeps deferred, queued, archiving, and verified archive states distinct from办理完成', () => {
    const deferred = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_deferred', archiveTask: null,
    })
    expect(deferred.history).toContainEqual(expect.objectContaining({
      id: 'archive-deferred', tone: 'complete', title: '草稿已保存并稍后处理',
    }))

    const queued = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_queued',
      archiveTask: { ...archiveTask, stage: 'queued', stage_label: '等待处理' },
    })
    expect(queued.systemStatus).toEqual(expect.objectContaining({ title: '后台归档处理中' }))
    expect(queued.history).toContainEqual(expect.objectContaining({
      id: 'archive-stage-queued', title: '后台归档处理中', detail: expect.stringContaining('可继续处理'),
    }))
    expect(queued.allActions.some(action => action.kind === 'pending_item')).toBe(true)

    const archiving = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archiving',
      archiveTask: { ...archiveTask, stage: 'hash', stage_label: '生成校验值' },
      photoState: 'uploading',
    })
    expect(archiving.history).toContainEqual(expect.objectContaining({
      id: 'archive-stage-hash', title: '后台归档处理中', detail: expect.stringContaining('正在生成文件校验值'),
    }))
    expect(archiving.systemStatus?.title).toBe('正在保存图片')

    const verified = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_verified',
      archiveTask: { ...archiveTask, status: 'succeeded', stage: 'completed', stage_label: '归档完成' },
      archiveMedium: 'optical_disc', archiveParts: [{ disc_number: null, size_bytes: 2048 }],
    })
    expect(verified.history).toContainEqual(expect.objectContaining({
      id: 'archive-completed', title: '后台归档已完成校验', detail: expect.stringContaining('仍需整理光盘编号'),
    }))
    expect(verified.history.map(item => item.title).join(' ')).not.toContain('办理完成')
  })

  it('separates single Word success from unified export completion', () => {
    const word = deriveGuidedReviewProjection({ ...buildInput(), wordExportSucceeded: true })
    expect(word.history).toContainEqual(expect.objectContaining({
      id: 'word-export-completed', title: 'Word 已导出',
    }))
    expect(word.history.some(item => item.title === '统一导出已完成')).toBe(false)

    const unified = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'exported', wordExportSucceeded: false,
      archiveMedium: 'hard_drive', archiveParts: [{ disc_number: 'YP20260825-01', size_bytes: 2048 }],
    })
    expect(unified.history).toContainEqual(expect.objectContaining({
      id: 'export-completed', title: '统一导出已完成',
    }))
    expect(unified.history.some(item => item.title === 'Word 已导出')).toBe(false)
  })
})
