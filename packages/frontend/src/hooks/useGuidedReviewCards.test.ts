import { act, renderHook } from '@testing-library/react'
import type { FieldState } from '@biji/shared/types'
import { describe, expect, it } from 'vitest'
import { REVIEW_TARGET_IDS } from './useReviewChecklist'
import type { GuidedReviewProjectionInput } from './useGuidedReviewCards'
import { deriveGuidedReviewProjection, useGuidedReviewCards } from './useGuidedReviewCards'
import { archiveTask, buildInput, syntheticReport, withMediumNumber } from './useGuidedReviewCards.testFixtures'

describe('guided review projection', () => {
  it('classifies existing facts without re-asking complete defaults or system-produced archive fields', () => {
    const report = {
      ...syntheticReport,
      inspection: {
        ...syntheticReport.inspection,
        software_tools: [{ name: 'SYNTHETIC-SOFTWARE', version: '1.0' }],
      },
    }
    const projection = deriveGuidedReviewProjection({ ...buildInput(report), caseSummaryReviewed: true })

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
      title: '文书与委托信息',
      fields: expect.arrayContaining([
        expect.objectContaining({ label: '文号', value: 'SYN-TEST〔2026〕001号' }),
        expect.objectContaining({ label: '委托人员', value: 'SYNTHETIC-PERSON' }),
      ]),
    }))
    expect(JSON.stringify(projection.history)).not.toContain('委托单位前缀')
    expect(JSON.stringify(projection.history)).not.toMatch(
      /SYNTHETIC-TASK|revision|Worker|worker|令牌|token|[A-Z]:\\/,
    )
    const inspectionFields = projection.history.find(item => item.id === 'fact-defaults')?.fields
    expect(inspectionFields).toContainEqual(expect.objectContaining({
      label: '软件工具 1', value: 'SYNTHETIC-SOFTWARE 1.0',
    }))
    expect(inspectionFields).not.toContainEqual(expect.objectContaining({ label: '主取证软件' }))
  })

  it('projects stable edit targets for previously handled document, date, and medium fields', () => {
    const report = {
      ...syntheticReport,
      attachments: {
        ...syntheticReport.attachments,
        disc_number: 'GP2026082501-01',
        burning_date: '2026年08月25日',
      },
    }
    const paths = [
      'document_number', 'introduction.entrust_time',
      'attachments.disc_number', 'attachments.burning_date',
    ]
    const fieldStates = Object.fromEntries(paths.map(path => [path, {
      field_path: path, source: 'user', confirmation: 'confirmed',
      revision: 1, last_changed_at: '2026-08-25T01:00:00Z',
    }])) as Record<string, FieldState>
    const projection = deriveGuidedReviewProjection({
      ...buildInput(report), fieldStates, caseSummaryReviewed: true,
    })
    const fields = projection.history.flatMap(item => item.fields || [])

    expect(fields).toEqual(expect.arrayContaining([
      expect.objectContaining({ label: '文号', userProvided: true, targetId: REVIEW_TARGET_IDS.documentNumber }),
      expect.objectContaining({ label: '委托时间', userProvided: true, targetId: REVIEW_TARGET_IDS.entrustTime }),
      expect.objectContaining({ label: '介质编号', userProvided: true, targetId: REVIEW_TARGET_IDS.discNumber }),
      expect.objectContaining({ label: '刻录时间', userProvided: true, targetId: REVIEW_TARGET_IDS.burningDate }),
    ]))
  })

  it('keeps operational states out of the Word content preview', () => {
    const running = deriveGuidedReviewProjection(buildInput())
    const completed = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_verified',
      archiveTask: { ...archiveTask, status: 'succeeded', stage: 'completed', stage_label: '归档完成' },
      archiveMedium: 'optical_disc', archiveParts: [{ disc_number: 'GP20260825-01', size_bytes: 2048 }],
    })

    expect(completed.history).toEqual(running.history)
    expect(JSON.stringify(completed.history)).not.toMatch(/来源已确认|归档|导出|保存状态|编辑权限/)
  })

  it('asks the user to review a prefilled case summary until it is confirmed in the page session', () => {
    const pending = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems: [], caseSummaryReviewed: false,
    })
    expect(pending.allActions).toContainEqual(expect.objectContaining({
      title: '请确认案件简要情况',
      pendingItem: expect.objectContaining({
        targetId: REVIEW_TARGET_IDS.caseSummary,
        kind: 'confirmation_required',
      }),
    }))

    const reviewed = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems: [], caseSummaryReviewed: true,
    })
    expect(reviewed.allActions.some(action =>
      action.pendingItem?.targetId === REVIEW_TARGET_IDS.caseSummary)).toBe(false)
  })

  it('places the prefilled case summary immediately after entrust time', () => {
    const pendingItems = [
      {
        id: 'SYNTHETIC-ENTRUST-TIME', sectionId: 'review-section-introduction',
        targetId: REVIEW_TARGET_IDS.entrustTime, sectionLabel: '一、绪论', fieldLabel: '委托时间',
        reason: '当前必填字段为空。', severity: 'warning' as const, kind: 'required_missing' as const,
      },
      {
        id: 'SYNTHETIC-REQUIREMENT', sectionId: 'review-section-introduction',
        targetId: REVIEW_TARGET_IDS.inspectionRequirement, sectionLabel: '一、绪论', fieldLabel: '检查要求',
        reason: '当前必填字段为空。', severity: 'warning' as const, kind: 'required_missing' as const,
      },
    ]
    const pending = deriveGuidedReviewProjection({
      ...buildInput(withMediumNumber(syntheticReport)), pendingItems, caseSummaryReviewed: false,
    })

    expect(pending.allActions.map(action => action.pendingItem?.targetId)).toEqual([
      REVIEW_TARGET_IDS.entrustTime,
      REVIEW_TARGET_IDS.caseSummary,
      REVIEW_TARGET_IDS.inspectionRequirement,
    ])
  })

  it('advances immediately after the page session confirms the case summary review', () => {
    const { result, rerender } = renderHook(({ reviewed }) => useGuidedReviewCards({
      ...buildInput(), pendingItems: [], caseSummaryReviewed: reviewed,
    }), { initialProps: { reviewed: false } })

    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.caseSummary)
    rerender({ reviewed: true })
    expect(result.current.currentAction?.kind).toBe('waiting')
  })

  it('updates structured history with user-supplemented evidence and per-material photo progress', () => {
    const recognizedEvidence = [1, 2].map(index => ({
      ...syntheticReport.introduction.evidence_list[0],
      id: `SYNTHETIC-RECOGNIZED-${index}`,
      evidence_id: `SYNTHETIC-RECOGNIZED-${index}`,
      evidence_number: `SYNTHETIC-R-${index}`,
    }))
    const userEvidence = [1, 2, 3].map(index => ({
      ...syntheticReport.introduction.evidence_list[0],
      id: `local-evidence-SYNTHETIC-${index}`,
      evidence_id: `local-evidence-SYNTHETIC-${index}`,
      evidence_number: `SYNTHETIC-U-${index}`,
      material_type_status: 'confirmed_by_user' as const,
      material_type_source: 'user' as const,
    }))
    const reportWith = (evidenceList: typeof recognizedEvidence) => ({
      ...syntheticReport,
      introduction: { ...syntheticReport.introduction, evidence_list: evidenceList },
      attachments: {
        ...syntheticReport.attachments,
        photo_ids: ['SYNTHETIC-PHOTO-1', 'SYNTHETIC-PHOTO-2', 'SYNTHETIC-PHOTO-3'],
      },
    })
    const { result, rerender } = renderHook(({ report }) => useGuidedReviewCards(buildInput(report)), {
      initialProps: { report: reportWith(recognizedEvidence) },
    })

    expect(result.current.history.find(item => item.id === 'fact-evidence')?.materials).toEqual([
      expect.objectContaining({ label: '检材 1 · SYNTHETIC-R-1', photoCount: 2, requiredPhotoCount: 2 }),
      expect.objectContaining({ label: '检材 2 · SYNTHETIC-R-2', photoCount: 1, requiredPhotoCount: 2 }),
    ])

    rerender({ report: reportWith([...recognizedEvidence, ...userEvidence]) })

    expect(result.current.history.find(item => item.id === 'fact-evidence')?.materials).toEqual([
      expect.objectContaining({ label: '检材 1 · SYNTHETIC-R-1' }),
      expect.objectContaining({ label: '检材 2 · SYNTHETIC-R-2' }),
      expect.objectContaining({ label: '检材 3 · SYNTHETIC-U-1', userProvided: true, sourceLabel: '人工添加' }),
      expect.objectContaining({ label: '检材 4 · SYNTHETIC-U-2' }),
      expect.objectContaining({ label: '检材 5 · SYNTHETIC-U-3' }),
    ])
  })

  it('refreshes history to the user-modified final value without retaining the recognized value', () => {
    const recognized = {
      ...syntheticReport,
      introduction: { ...syntheticReport.introduction, entrust_persons: ['SYNTHETIC-RECOGNIZED-PERSON'] },
    }
    const recognizedFieldState: FieldState = {
      field_path: 'introduction.entrust_persons', source: 'report', confirmation: 'confirmed',
      revision: 0, last_changed_at: '2026-08-25T01:00:00Z',
    }
    const { result, rerender } = renderHook(({ report, fieldState }) => useGuidedReviewCards({
      ...buildInput(report), fieldStates: { 'introduction.entrust_persons': fieldState },
    }), {
      initialProps: { report: recognized, fieldState: recognizedFieldState },
    })

    rerender({
      report: {
        ...recognized,
        introduction: { ...recognized.introduction, entrust_persons: [
          'SYNTHETIC-USER-PERSON-A', 'SYNTHETIC-USER-PERSON-B',
        ] },
      },
      fieldState: { ...recognizedFieldState, source: 'user', revision: 1 },
    })

    const fields = result.current.history.find(item => item.id === 'fact-report-recognition')?.fields
    expect(fields).toContainEqual(expect.objectContaining({
      label: '委托人员', value: 'SYNTHETIC-USER-PERSON-A、SYNTHETIC-USER-PERSON-B', userProvided: true,
    }))
    expect(JSON.stringify(fields)).not.toContain('SYNTHETIC-RECOGNIZED-PERSON')

    rerender({
      report: {
        ...recognized,
        introduction: { ...recognized.introduction, entrust_persons: [] },
      },
      fieldState: { ...recognizedFieldState, source: 'user', revision: 2 },
    })
    expect(result.current.history.find(item => item.id === 'fact-report-recognition')?.fields)
      .not.toContainEqual(expect.objectContaining({ label: '委托人员' }))
  })

  it('keeps the current action stable when a background fact adds a higher-priority item', () => {
    const initial = buildInput(withMediumNumber({ ...syntheticReport, document_number: '' }))
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

    act(() => result.current.returnToNextAction())
    expect(result.current.currentAction?.kind).toBe('source_recovery')

    rerender({ input: buildInput() })
    expect(result.current.history.some(item => item.id.startsWith('completed-'))).toBe(false)
  })

  it('keeps a completed text action current until Enter confirms it', () => {
    const initial = buildInput(withMediumNumber({ ...syntheticReport, document_number: '' }))
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: initial },
    })
    const documentActionId = result.current.currentAction?.id

    rerender({ input: buildInput(withMediumNumber({ ...syntheticReport, document_number: 'S' })) })

    expect(result.current.currentAction?.id).toBe(documentActionId)
    expect(result.current.allActions.some(action => action.id === documentActionId)).toBe(true)
    expect(result.current.history.some(item => item.id.startsWith('completed-'))).toBe(false)

    act(() => result.current.confirmCurrentAction())

    expect(result.current.currentAction?.id).not.toBe(documentActionId)
    expect(result.current.allActions.some(action => action.id === documentActionId)).toBe(false)
    expect(result.current.history.find(item => item.id === 'fact-report-recognition')?.fields)
      .toContainEqual(expect.objectContaining({ label: '文号', value: 'S' }))
  })

  it('returns to the prior pending field after switching to the photo action', () => {
    const report = {
      ...syntheticReport,
      document_number: '',
      attachments: { ...syntheticReport.attachments, photo_ids: [], disc_number: 'GP2026082501-01' },
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
    const initial = buildInput(withMediumNumber({ ...syntheticReport, document_number: '' }))
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: initial },
    })
    const documentActionId = result.current.currentAction?.id

    rerender({ input: buildInput(withMediumNumber({
      ...syntheticReport, document_number: 'SYN-TEST〔2026〕009号',
    })) })
    act(() => result.current.confirmCurrentAction())

    const nextActionId = result.current.currentAction?.id
    expect(nextActionId).not.toBe(documentActionId)
    expect(result.current.previousAction?.id).toBe(documentActionId)

    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.id).toBe(documentActionId)
    expect(result.current.isReviewingPrevious).toBe(true)
    expect(result.current.allActions.some(action => action.id === documentActionId)).toBe(false)

    act(() => result.current.returnToNextAction())
    expect(result.current.currentAction?.id).toBe(nextActionId)
    expect(result.current.isReviewingPrevious).toBe(false)

    const completedAction = result.current.previousAction!
    act(() => result.current.revisitAction(completedAction))
    expect(result.current.currentAction?.id).toBe(documentActionId)
    expect(result.current.isReviewingPrevious).toBe(true)
  })

  it('opens a previously handled evidence confirmation from the ready state', () => {
    const completenessPath = 'introduction.evidence_list.completeness'
    const fieldStates = { [completenessPath]: {
      field_path: completenessPath, source: 'user', confirmation: 'confirmed',
      revision: 1, last_changed_at: '2026-08-25T01:00:00Z',
    } } as Record<string, FieldState>
    const { result } = renderHook(() => useGuidedReviewCards({
      ...buildInput(), pendingItems: [], fieldStates, caseSummaryReviewed: true, lifecycle: 'archive_verified',
      archiveParts: [{ disc_number: 'GP20260825-01', size_bytes: 2048 }],
    }))
    const completeness = result.current.previouslyHandledFields.find(
      field => field.targetId === REVIEW_TARGET_IDS.evidenceCompleteness)
    expect(result.current.currentAction?.kind).toBe('ready')
    expect(completeness).toBeTruthy()
    act(() => result.current.revisitHandledField(completeness!))
    expect(result.current.currentAction).toEqual(expect.objectContaining({
      kind: 'pending_item',
      title: '请确认检材完整性',
      pendingItem: expect.objectContaining({ targetId: REVIEW_TARGET_IDS.evidenceCompleteness }),
    }))
    act(() => result.current.selectAction('ready'))
    expect(result.current.currentAction?.kind).toBe('ready')
  })
  it('navigates backward and forward across the full session action trail', () => {
    const { result } = renderHook(() => useGuidedReviewCards(buildInput(withMediumNumber({
      ...syntheticReport,
      document_number: '',
      introduction: { ...syntheticReport.introduction, entrust_time: '', case_summary: '' },
    }))))
    const pendingActions = result.current.allActions.filter(action => action.kind === 'pending_item')
    expect(pendingActions.length).toBeGreaterThanOrEqual(3)
    const [firstAction, secondAction, thirdAction] = pendingActions

    act(() => result.current.selectAction(secondAction.id))
    act(() => result.current.selectAction(thirdAction.id))
    expect(result.current.currentAction?.id).toBe(thirdAction.id)
    expect(result.current.canReturnToPrevious).toBe(true)
    expect(result.current.canReturnToNext).toBe(false)

    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.id).toBe(secondAction.id)
    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.id).toBe(firstAction.id)
    expect(result.current.canReturnToPrevious).toBe(false)
    expect(result.current.canReturnToNext).toBe(true)

    act(() => result.current.returnToNextAction())
    expect(result.current.currentAction?.id).toBe(secondAction.id)
    act(() => result.current.returnToNextAction())
    expect(result.current.currentAction?.id).toBe(thirdAction.id)
    expect(result.current.canReturnToNext).toBe(false)
  })

  it('does not place autosave or recovery states between user-handled steps', () => {
    const initial = buildInput(withMediumNumber({
      ...syntheticReport,
      document_number: '',
      introduction: { ...syntheticReport.introduction, entrust_time: '' },
    }))
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: initial },
    })
    const documentActionId = result.current.currentAction?.id

    rerender({ input: {
      ...buildInput(withMediumNumber({
        ...syntheticReport,
        document_number: 'SYN-TEST〔2026〕010号',
        introduction: { ...syntheticReport.introduction, entrust_time: '' },
      })),
      saveState: 'saving',
      saveHasPending: true,
    } })
    act(() => result.current.confirmCurrentAction())

    expect(result.current.currentAction?.kind).toBe('pending_item')
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('委托时间')
    expect(result.current.allActions.some(action => action.kind === 'save_recovery')).toBe(false)

    rerender({ input: {
      ...buildInput(withMediumNumber({
        ...syntheticReport,
        document_number: 'SYN-TEST〔2026〕010号',
        introduction: { ...syntheticReport.introduction, entrust_time: '' },
      })),
      saveState: 'failed',
      saveHasPending: true,
    } })
    expect(result.current.allActions.some(action => action.kind === 'save_recovery')).toBe(true)

    act(() => result.current.selectAction('save-recovery'))
    expect(result.current.currentAction?.kind).toBe('save_recovery')
    expect(result.current.canReturnToPrevious).toBe(false)
    expect(result.current.canReturnToNext).toBe(false)

    rerender({ input: buildInput(withMediumNumber({
      ...syntheticReport,
      document_number: 'SYN-TEST〔2026〕010号',
      introduction: { ...syntheticReport.introduction, entrust_time: '' },
    })) })
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('委托时间')

    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.id).toBe(documentActionId)
    expect(result.current.currentAction?.kind).toBe('pending_item')
    expect(result.current.canReturnToPrevious).toBe(false)
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
    expect(pending.allActions.map(action => action.title)).toEqual(['请输入文号', '请选择委托时间', '请确认检材完整性'])
    expect(pending.allActions[2]?.advanceOnEnter).toBe(true)

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
    expect(ready.allActions[0]?.title).toBe('当前审核已完成')
    expect(ready.allActions[0]?.description).toBe('请保存并退出；返回案件工作台后可统一导出。')
  })

  it('recommends compression, medium number, then ordinary review fields', () => {
    const pendingItems = [
      {
        id: 'SYNTHETIC-DOCUMENT', sectionId: 'review-section-document',
        targetId: REVIEW_TARGET_IDS.documentNumber, sectionLabel: '文书信息', fieldLabel: '文号',
        reason: '当前必填字段为空。', severity: 'warning' as const, kind: 'required_missing' as const,
      },
      {
        id: 'SYNTHETIC-MEDIUM', sectionId: 'review-section-archive',
        targetId: REVIEW_TARGET_IDS.discNumber, sectionLabel: '附件', fieldLabel: '介质编号',
        reason: '当前必填字段为空。', severity: 'warning' as const, kind: 'required_missing' as const,
      },
    ]
    const ready = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems, lifecycle: 'review_ready', archiveTask: null,
    })
    expect(ready.allActions.map(action => action.title)).toEqual([
      '请选择压缩时机', '请输入介质编号', '请输入文号',
    ])

    const deferred = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems, lifecycle: 'archive_deferred', archiveTask: null,
    })
    expect(deferred.allActions.map(action => action.title)).toEqual([
      '请输入介质编号', '请输入文号', '请选择压缩时机',
    ])

    const recovering = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems, lifecycle: 'review_ready', archiveTask: null,
      saveState: 'failed', saveHasPending: true,
    })
    expect(recovering.allActions.slice(0, 2).map(action => action.title)).toEqual([
      '请恢复草稿保存', '请选择压缩时机',
    ])
  })

  it('keeps save and lease recovery in actions without adding them to the Word preview', () => {
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
    expect(JSON.stringify(result.current.history)).not.toMatch(/草稿保存|编辑权限/)

    rerender({ input: { ...buildInput(), saveState: 'saved', saveHasPending: false } })
    expect(JSON.stringify(result.current.history)).not.toMatch(/草稿保存|编辑权限/)
    expect(result.current.allActions.some(action => ['save_recovery', 'lease_recovery'].includes(action.kind))).toBe(false)
  })

  it('keeps attachment recovery in actions without adding export status to the Word preview', () => {
    const warning: GuidedReviewProjectionInput = { ...buildInput(), photoState: 'warning' }
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: warning },
    })

    expect(result.current.allActions).toContainEqual(expect.objectContaining({
      id: 'photo-recovery', kind: 'photo_recovery', title: '请检查附件2图片',
    }))
    expect(JSON.stringify(result.current.history)).not.toMatch(/Word 已导出|附件2已省略/)

    rerender({ input: buildInput() })
    expect(JSON.stringify(result.current.history)).not.toMatch(/附件2图片状态已恢复/)
    expect(result.current.allActions.some(action => action.kind === 'photo_recovery')).toBe(false)
  })

  it('keeps archive states distinct in actions and system status, outside the Word preview', () => {
    const deferred = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_deferred', archiveTask: null,
    })
    expect(JSON.stringify(deferred.history)).not.toMatch(/稍后处理|归档/)

    const queued = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_queued',
      archiveTask: { ...archiveTask, stage: 'queued', stage_label: '等待处理' },
    })
    expect(queued.systemStatus).toEqual(expect.objectContaining({ title: '后台归档处理中' }))
    expect(JSON.stringify(queued.history)).not.toMatch(/后台归档处理中/)
    expect(queued.allActions.some(action => action.kind === 'pending_item')).toBe(true)

    const archiving = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archiving',
      archiveTask: { ...archiveTask, stage: 'hash', stage_label: '生成校验值' },
      photoState: 'uploading',
    })
    expect(JSON.stringify(archiving.history)).not.toMatch(/正在生成文件校验值/)
    expect(archiving.systemStatus?.title).toBe('正在保存图片')

    const verified = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_verified',
      archiveTask: { ...archiveTask, status: 'succeeded', stage: 'completed', stage_label: '归档完成' },
      archiveMedium: 'optical_disc', archiveParts: [{ disc_number: null, size_bytes: 2048 }],
    })
    expect(JSON.stringify(verified.history)).not.toMatch(/归档|办理完成/)
  })

  it('keeps single Word and unified export status out of the Word content preview', () => {
    const word = deriveGuidedReviewProjection({ ...buildInput(), wordExportSucceeded: true })
    expect(JSON.stringify(word.history)).not.toMatch(/Word 已导出|统一导出已完成/)

    const unified = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'exported', wordExportSucceeded: false,
      archiveMedium: 'hard_drive', archiveParts: [{ disc_number: 'YP20260825-01', size_bytes: 2048 }],
    })
    expect(unified.history).toEqual(word.history)
  })
})
