import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { REVIEW_TARGET_IDS } from './useReviewChecklist'
import { deriveGuidedReviewProjection, useGuidedReviewCards } from './useGuidedReviewCards'
import { buildInput, syntheticReport, withMediumNumber } from './useGuidedReviewCards.testFixtures'

beforeEach(() => window.localStorage.clear())

const discNumberItem = {
  id: 'SYNTHETIC-MEDIUM',
  sectionId: 'review-section-archive',
  targetId: REVIEW_TARGET_IDS.discNumber,
  sectionLabel: '附件',
  fieldLabel: '介质编号',
  reason: '当前必填字段为空。',
  severity: 'warning' as const,
  kind: 'required_missing' as const,
}

const photoItem = {
  id: 'SYNTHETIC-PHOTOS',
  sectionId: 'review-section-attachments',
  targetId: REVIEW_TARGET_IDS.photos,
  sectionLabel: '附件',
  fieldLabel: '检材照片',
  reason: '还需上传 2 张图片（每个检材需 2 张）。',
  severity: 'warning' as const,
  kind: 'required_missing' as const,
}

const documentItem = {
  id: 'SYNTHETIC-DOCUMENT',
  sectionId: 'review-section-document',
  targetId: REVIEW_TARGET_IDS.documentNumber,
  sectionLabel: '文书信息',
  fieldLabel: '文号',
  reason: '当前必填字段为空。',
  severity: 'warning' as const,
  kind: 'required_missing' as const,
}

describe('guided review deferred archive navigation', () => {
  it('keeps medium number after photo upload in the normal review sequence', () => {
    const pendingItems = [documentItem, photoItem, discNumberItem]
    const ready = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems, lifecycle: 'review_ready', archiveTask: null,
    })
    expect(ready.allActions.map(action => action.title)).toEqual([
      '请选择压缩时机', '请输入文号', '请上传检材照片', '请输入介质编号',
    ])

    const deferred = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems, lifecycle: 'archive_deferred', archiveTask: null,
    })
    expect(deferred.allActions.map(action => action.title)).toEqual([
      '请输入文号', '请上传检材照片', '请输入介质编号', '请选择压缩时机',
    ])

    const recovering = deriveGuidedReviewProjection({
      ...buildInput(), pendingItems, lifecycle: 'review_ready', archiveTask: null,
      saveState: 'failed', saveHasPending: true,
    })
    expect(recovering.allActions.slice(0, 2).map(action => action.title)).toEqual([
      '请恢复草稿保存', '请选择压缩时机',
    ])
  })

  it('continues to the next review item after choosing deferred while keeping compression revisitable', () => {
    const input = {
      ...buildInput(syntheticReport), pendingItems: [discNumberItem],
      lifecycle: 'review_ready' as const, archiveTask: null, caseSummaryReviewed: true,
    }
    const { result, rerender } = renderHook(({ lifecycle }) => useGuidedReviewCards({
      ...input, lifecycle,
    }), { initialProps: { lifecycle: 'review_ready' as 'review_ready' | 'archive_deferred' } })

    expect(result.current.currentAction?.kind).toBe('archive_decision')
    rerender({ lifecycle: 'archive_deferred' })

    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.discNumber)
    expect(result.current.allActions.at(-1)?.kind).toBe('archive_decision')

    act(() => result.current.selectAction('archive-decision'))
    expect(result.current.currentAction?.kind).toBe('archive_decision')
  })

  it('shows a completed deferred state instead of forcing compression when no review item remains', () => {
    const projection = deriveGuidedReviewProjection({
      ...buildInput(withMediumNumber(syntheticReport)), pendingItems: [],
      lifecycle: 'archive_deferred', archiveTask: null, caseSummaryReviewed: true,
    })

    expect(projection.allActions.map(action => action.kind)).toEqual([
      'archive_deferred', 'archive_decision',
    ])
    expect(projection.allActions[0]?.title).toBe('草稿已保存')
    expect(projection.allActions[0]?.description).toContain('压缩已设为稍后处理')
  })

  it('removes an obsolete archive decision after immediate archiving starts', async () => {
    const input = {
      ...buildInput(syntheticReport), pendingItems: [documentItem], archiveTask: null,
      caseSummaryReviewed: true,
    }
    const view = renderHook(({ lifecycle }) => useGuidedReviewCards({ ...input, lifecycle }), {
      initialProps: { lifecycle: 'review_ready' as 'review_ready' | 'archive_queued' },
    })
    expect(view.result.current.currentAction?.kind).toBe('archive_decision')

    view.rerender({ lifecycle: 'archive_queued' })

    await waitFor(() => expect(view.result.current.currentAction?.pendingItem?.targetId)
      .toBe(REVIEW_TARGET_IDS.documentNumber))
    expect(view.result.current.allActions.some(action => action.kind === 'archive_decision')).toBe(false)
    expect(view.result.current.canReturnToPrevious).toBe(false)
  })

  it('does not claim a deferred draft was saved while saving is unsettled', () => {
    const projection = deriveGuidedReviewProjection({
      ...buildInput(withMediumNumber(syntheticReport)), pendingItems: [],
      lifecycle: 'archive_deferred', archiveTask: null, caseSummaryReviewed: true,
      saveState: 'saving', saveHasPending: true,
    })

    expect(projection.allActions[0]).toEqual(expect.objectContaining({
      kind: 'waiting', title: '请稍候，正在保存当前输入',
    }))
    expect(projection.allActions.some(action => action.kind === 'archive_deferred')).toBe(false)
  })
})
