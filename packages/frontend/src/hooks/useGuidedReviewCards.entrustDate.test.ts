import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { REVIEW_TARGET_IDS } from './useReviewChecklist'
import { useGuidedReviewCards } from './useGuidedReviewCards'
import { buildInput, syntheticReport, withMediumNumber } from './useGuidedReviewCards.testFixtures'

describe('guided entrust date confirmation', () => {
  it('keeps entrust date edits on the current step until explicit confirmation', () => {
    const initialReport = withMediumNumber({
      ...syntheticReport,
      introduction: { ...syntheticReport.introduction, entrust_time: '', case_summary: '' },
    })
    const { result, rerender } = renderHook(({ report }) => useGuidedReviewCards(buildInput(report)), {
      initialProps: { report: initialReport },
    })
    const dateAction = result.current.allActions.find(
      action => action.pendingItem?.targetId === REVIEW_TARGET_IDS.entrustTime)!
    act(() => result.current.selectAction(dateAction.id))
    act(() => result.current.confirmCurrentAction())
    expect(result.current.currentAction?.id).toBe(dateAction.id)

    // SYNTHETIC: native pickers can emit valid intermediate dates while selecting a month.
    for (const value of ['2026年09月01日', '2026年10月01日', '', '2026年10月15日']) {
      rerender({ report: {
        ...initialReport, introduction: { ...initialReport.introduction, entrust_time: value },
      } })
      expect(result.current.currentAction?.id).toBe(dateAction.id)
    }
    expect(result.current.currentAction?.requiresExplicitAdvance).toBe(true)
    expect(result.current.currentAction?.advanceOnEnter).toBe(false)
    act(() => result.current.confirmCurrentAction())
    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.caseSummary)
    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.id).toBe(dateAction.id)
  })

})
