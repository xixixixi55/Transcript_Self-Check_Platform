import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { REVIEW_TARGET_IDS } from './useReviewChecklist'
import { useGuidedReviewCards, type GuidedReviewProjectionInput } from './useGuidedReviewCards'
import { buildInput, syntheticReport, withMediumNumber } from './useGuidedReviewCards.testFixtures'

describe('guided photo review navigation', () => {
  it('keeps the photo action current after a complete batch import until the user advances', () => {
    const incompleteReport = withMediumNumber({
      ...syntheticReport,
      document_number: '',
      attachments: { ...syntheticReport.attachments, photo_ids: [] },
    })
    const { result, rerender } = renderHook(({ report }) => useGuidedReviewCards(buildInput(report)), {
      initialProps: { report: incompleteReport },
    })
    const photoAction = result.current.allActions.find(
      action => action.pendingItem?.targetId === REVIEW_TARGET_IDS.photos,
    )
    act(() => result.current.selectAction(photoAction!.id))

    rerender({ report: {
      ...incompleteReport,
      attachments: {
        ...incompleteReport.attachments,
        photo_ids: ['SYNTHETIC-BATCH-PHOTO-1', 'SYNTHETIC-BATCH-PHOTO-2'],
      },
    } })

    expect(result.current.currentAction?.id).toBe(photoAction?.id)
    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.photos)
    expect(result.current.allActions.some(action => action.id === photoAction?.id)).toBe(true)

    act(() => result.current.confirmCurrentAction())

    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.documentNumber)
    expect(result.current.allActions.some(action => action.id === photoAction?.id)).toBe(false)
  })

  it('keeps the photo action current when it became active after a recovery action', () => {
    const incompleteReport = withMediumNumber({
      ...syntheticReport,
      attachments: { ...syntheticReport.attachments, photo_ids: [] },
    })
    const { result, rerender } = renderHook(({ report, saveState, saveHasPending }) => {
      const input = buildInput(report)
      return useGuidedReviewCards({
        ...input,
        pendingItems: input.pendingItems.filter(item => item.targetId === REVIEW_TARGET_IDS.photos),
        saveState,
        saveHasPending,
      })
    }, {
      initialProps: {
        report: incompleteReport,
        saveState: 'failed' as GuidedReviewProjectionInput['saveState'],
        saveHasPending: true,
      },
    })

    expect(result.current.currentAction?.kind).toBe('save_recovery')

    rerender({ report: incompleteReport, saveState: 'saved' as const, saveHasPending: false })
    const photoAction = result.current.currentAction
    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.photos)

    rerender({
      report: {
        ...incompleteReport,
        attachments: {
          ...incompleteReport.attachments,
          photo_ids: ['SYNTHETIC-RECOVERED-PHOTO-1', 'SYNTHETIC-RECOVERED-PHOTO-2'],
        },
      },
      saveState: 'saved' as const,
      saveHasPending: false,
    })

    expect(result.current.currentAction?.id).toBe(photoAction?.id)
  })

  it('keeps one stable backward and forward trail from evidence through photos to deferred completion', () => {
    const incompleteReport = withMediumNumber({
      ...syntheticReport,
      attachments: { ...syntheticReport.attachments, photo_ids: [] },
    })
    const initial = buildInput(incompleteReport)
    const evidenceAction = {
      id: 'SYNTHETIC-EVIDENCE-COMPLETENESS',
      sectionId: 'review-section-introduction',
      targetId: REVIEW_TARGET_IDS.evidenceCompleteness,
      sectionLabel: '一、绪论',
      fieldLabel: '检材完整性',
      reason: '请确认检材完整性。',
      severity: 'warning' as const,
      kind: 'confirmation_required' as const,
    }
    const photoItem = initial.pendingItems.find(item => item.targetId === REVIEW_TARGET_IDS.photos)!
    const inputFor = (report: typeof incompleteReport, pendingItems: typeof initial.pendingItems) => ({
      ...buildInput(report),
      lifecycle: 'archive_deferred' as const,
      archiveTask: null,
      pendingItems,
    })
    const { result, rerender } = renderHook(({ report, pendingItems }) => useGuidedReviewCards(
      inputFor(report, pendingItems),
    ), {
      initialProps: { report: incompleteReport, pendingItems: [evidenceAction, photoItem] },
    })

    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.evidenceCompleteness)
    rerender({ report: incompleteReport, pendingItems: [photoItem] })
    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.photos)
    expect(result.current.canReturnToPrevious).toBe(true)

    const completedReport = {
      ...incompleteReport,
      attachments: {
        ...incompleteReport.attachments,
        photo_ids: ['SYNTHETIC-FLOW-PHOTO-1', 'SYNTHETIC-FLOW-PHOTO-2'],
      },
    }
    rerender({ report: completedReport, pendingItems: [] })
    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.photos)
    expect(result.current.canReturnToPrevious).toBe(true)

    act(() => result.current.confirmCurrentAction())
    expect(result.current.currentAction?.kind).toBe('archive_deferred')
    expect(result.current.canReturnToPrevious).toBe(true)
    expect(result.current.canReturnToNext).toBe(false)

    act(() => result.current.returnToPreviousAction())
    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.photos)
    act(() => result.current.returnToNextAction())
    expect(result.current.currentAction?.kind).toBe('archive_deferred')
  })

  it('reopens completed photos from previously handled without restoring a pending count', () => {
    const report = withMediumNumber(syntheticReport)
    const { result } = renderHook(() => useGuidedReviewCards({
      ...buildInput(report), caseSummaryReviewed: true,
    }))
    const photoField = result.current.previouslyHandledFields.find(
      field => field.targetId === REVIEW_TARGET_IDS.photos,
    )

    expect(result.current.allActions.some(
      action => action.pendingItem?.targetId === REVIEW_TARGET_IDS.photos,
    )).toBe(false)
    expect(photoField).toEqual(expect.objectContaining({
      label: '检材照片', value: '已上传 2 张图片', userProvided: true,
    }))

    act(() => result.current.revisitHandledField(photoField!))

    expect(result.current.currentAction).toEqual(expect.objectContaining({
      title: '请核对检材照片', requiresExplicitAdvance: true,
      pendingItem: expect.objectContaining({ targetId: REVIEW_TARGET_IDS.photos }),
    }))
  })

  it('keeps one usable photo step when binding reports an error', () => {
    const incompleteReport = withMediumNumber({
      ...syntheticReport,
      attachments: { ...syntheticReport.attachments, photo_ids: [] },
    })
    const { result, rerender } = renderHook(({ report, photoState }) => useGuidedReviewCards({
      ...buildInput(report), photoState,
    }), {
      initialProps: { report: incompleteReport, photoState: 'error' as const },
    })
    const photoActions = result.current.allActions.filter(
      action => action.kind === 'photo_recovery'
        || action.pendingItem?.targetId === REVIEW_TARGET_IDS.photos,
    )

    expect(photoActions).toHaveLength(1)
    expect(photoActions[0]).toEqual(expect.objectContaining({
      kind: 'pending_item',
      pendingItem: expect.objectContaining({ targetId: REVIEW_TARGET_IDS.photos }),
    }))
    act(() => result.current.selectAction(photoActions[0].id))

    rerender({
      report: {
        ...incompleteReport,
        attachments: {
          ...incompleteReport.attachments,
          photo_ids: ['SYNTHETIC-RACE-PHOTO-1', 'SYNTHETIC-RACE-PHOTO-2'],
        },
      },
      photoState: 'error' as const,
    })

    expect(result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.photos)
    expect(result.current.allActions.filter(
      action => action.kind === 'photo_recovery'
        || action.pendingItem?.targetId === REVIEW_TARGET_IDS.photos,
    )).toHaveLength(1)
  })
})
