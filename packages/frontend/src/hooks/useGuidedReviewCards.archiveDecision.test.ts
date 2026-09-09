import { act, renderHook } from '@testing-library/react'
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

describe('guided review deferred archive navigation', () => {
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
})
