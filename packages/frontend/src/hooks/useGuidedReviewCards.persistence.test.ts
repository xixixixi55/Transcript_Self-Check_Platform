import { act, renderHook, waitFor } from '@testing-library/react'
import type { FieldState, InspectionReport } from '@biji/shared/types'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { REVIEW_TARGET_IDS } from './useReviewChecklist'
import {
  guidedReviewNavigationStorageKey,
  readGuidedReviewNavigationCheckpoint,
} from './useGuidedReviewNavigationPersistence'
import { useGuidedReviewCards, type GuidedReviewProjectionInput } from './useGuidedReviewCards'
import { buildInput, syntheticReport, withMediumNumber } from './useGuidedReviewCards.testFixtures'

function journeyInput(caseId = 'SYNTHETIC-CASE-PERSISTENCE') {
  const report: InspectionReport = withMediumNumber({
    ...syntheticReport,
    document_number: '',
    introduction: {
      ...syntheticReport.introduction,
      entrust_time: '',
    },
  })
  return {
    ...buildInput(report),
    caseId,
    caseSummaryReviewed: false,
  }
}

function selectTarget(
  result: { current: ReturnType<typeof useGuidedReviewCards> },
  targetId: string,
) {
  const action = result.current.allActions.find(candidate => candidate.pendingItem?.targetId === targetId)
  expect(action).toBeTruthy()
  act(() => result.current.selectAction(action!.id))
}

describe('guided review navigation persistence', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('restores the current case-summary step and the full back-forward trail after remounting', () => {
    const first = renderHook(() => useGuidedReviewCards(journeyInput()))
    expect(first.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.documentNumber)

    selectTarget(first.result, REVIEW_TARGET_IDS.entrustTime)
    selectTarget(first.result, REVIEW_TARGET_IDS.caseSummary)
    expect(first.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.caseSummary)
    first.unmount()

    const reopened = renderHook(() => useGuidedReviewCards(journeyInput()))
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.caseSummary)
    expect(reopened.result.current.canReturnToPrevious).toBe(true)

    act(() => reopened.result.current.returnToPreviousAction())
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.entrustTime)
    act(() => reopened.result.current.returnToPreviousAction())
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.documentNumber)
    expect(reopened.result.current.canReturnToPrevious).toBe(false)

    act(() => reopened.result.current.returnToNextAction())
    act(() => reopened.result.current.returnToNextAction())
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.caseSummary)
    expect(reopened.result.current.canReturnToNext).toBe(false)
  })

  it('does not append the restored middle step to the trail tail and create a forward loop', () => {
    const first = renderHook(() => useGuidedReviewCards(journeyInput()))
    selectTarget(first.result, REVIEW_TARGET_IDS.entrustTime)
    selectTarget(first.result, REVIEW_TARGET_IDS.caseSummary)
    act(() => first.result.current.returnToPreviousAction())
    expect(first.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.entrustTime)
    first.unmount()

    const reopened = renderHook(() => useGuidedReviewCards(journeyInput()))
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.entrustTime)
    act(() => reopened.result.current.returnToNextAction())
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.caseSummary)
    expect(reopened.result.current.canReturnToNext).toBe(false)
  })

  it('isolates checkpoints by case and stores no report field values', () => {
    const first = renderHook(() => useGuidedReviewCards(journeyInput('SYNTHETIC-CASE-A')))
    selectTarget(first.result, REVIEW_TARGET_IDS.caseSummary)
    first.unmount()

    expect(window.localStorage.length).toBe(1)
    const serializedStorage = JSON.stringify(window.localStorage)
    expect(serializedStorage).not.toContain(syntheticReport.introduction.case_summary)
    expect(serializedStorage).not.toContain(syntheticReport.document_number)

    const secondCase = renderHook(() => useGuidedReviewCards(journeyInput('SYNTHETIC-CASE-B')))
    expect(secondCase.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.documentNumber)
    expect(secondCase.result.current.canReturnToPrevious).toBe(false)
  })

  it('rebuilds completed manual steps when the current checkpoint step is no longer pending', () => {
    const first = renderHook(() => useGuidedReviewCards(journeyInput()))
    selectTarget(first.result, REVIEW_TARGET_IDS.caseSummary)
    first.unmount()

    const currentFacts = {
      ...buildInput(withMediumNumber({
        ...syntheticReport,
        attachments: { ...syntheticReport.attachments, burning_date: '2026年08月25日' },
      })),
      caseId: 'SYNTHETIC-CASE-PERSISTENCE',
      pendingItems: [],
      caseSummaryReviewed: true,
      fieldStates: {
        document_number: {
          field_path: 'document_number', source: 'user' as const,
          confirmation: 'confirmed' as const, revision: 1,
          last_changed_at: '2026-09-10T16:59:00Z',
        },
        'introduction.evidence_list.completeness': {
          field_path: 'introduction.evidence_list.completeness', source: 'user' as const,
          confirmation: 'confirmed' as const, revision: 2,
          last_changed_at: '2026-09-10T17:00:00Z',
        },
        'attachments.burning_date': {
          field_path: 'attachments.burning_date', source: 'user' as const,
          confirmation: 'confirmed' as const, revision: 3,
          last_changed_at: '2026-09-10T17:01:00Z',
        },
      },
    }
    const reopened = renderHook(() => useGuidedReviewCards(currentFacts))
    expect(reopened.result.current.currentAction?.pendingItem?.targetId)
      .toBe(REVIEW_TARGET_IDS.documentNumber)
    expect(readGuidedReviewNavigationCheckpoint('SYNTHETIC-CASE-PERSISTENCE')?.entries
      .map(entry => entry.targetId)).toEqual([
      REVIEW_TARGET_IDS.documentNumber,
      REVIEW_TARGET_IDS.evidenceCompleteness,
      REVIEW_TARGET_IDS.photos,
      REVIEW_TARGET_IDS.burningDate,
    ])
    expect(reopened.result.current.canReturnToPrevious).toBe(false)
    expect(reopened.result.current.canReturnToNext).toBe(true)

    act(() => reopened.result.current.returnToNextAction())
    expect(reopened.result.current.currentAction?.pendingItem?.targetId)
      .toBe(REVIEW_TARGET_IDS.evidenceCompleteness)
    act(() => reopened.result.current.returnToNextAction())
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.photos)
    act(() => reopened.result.current.returnToNextAction())
    expect(reopened.result.current.currentAction).toEqual(expect.objectContaining({
      pendingItem: expect.objectContaining({ targetId: REVIEW_TARGET_IDS.burningDate }),
    }))
    expect(reopened.result.current.canReturnToNext).toBe(true)
    act(() => reopened.result.current.returnToNextAction())
    expect(reopened.result.current.currentAction?.kind).toBe('ready')
    expect(reopened.result.current.canReturnToNext).toBe(false)
  })

  it('waits for current case facts before restoring an existing checkpoint', async () => {
    const first = renderHook(() => useGuidedReviewCards(journeyInput()))
    selectTarget(first.result, REVIEW_TARGET_IDS.caseSummary)
    first.unmount()
    const checkpoint = readGuidedReviewNavigationCheckpoint('SYNTHETIC-CASE-PERSISTENCE')
    expect(checkpoint?.entries[checkpoint.index].targetId).toBe(REVIEW_TARGET_IDS.caseSummary)

    const loadingInput: GuidedReviewProjectionInput = {
      ...journeyInput(),
      report: null,
      pendingItems: [],
    }
    const reopened = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: loadingInput },
    })
    expect(reopened.result.current.currentAction).toBeNull()
    expect(window.localStorage.length).toBe(1)

    reopened.rerender({ input: journeyInput() })
    await waitFor(() => expect(reopened.result.current.currentAction?.pendingItem?.targetId)
      .toBe(REVIEW_TARGET_IDS.caseSummary))
    expect(reopened.result.current.canReturnToPrevious).toBe(true)
  })

  it('rebuilds a completed earlier step from current draft facts instead of stored values', () => {
    const initial = journeyInput()
    const first = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: initial },
    })
    const completedReport = {
      ...initial.report!,
      document_number: 'SYN-TEST〔2026〕010号',
      introduction: {
        ...initial.report!.introduction,
        entrust_time: syntheticReport.introduction.entrust_time,
      },
    }
    const documentState: FieldState = {
      field_path: 'document_number', source: 'user', confirmation: 'confirmed',
      revision: 2, last_changed_at: '2026-09-09T12:00:00Z',
    }
    first.rerender({ input: {
      ...journeyInput(),
      report: completedReport,
      fieldStates: { document_number: documentState },
      pendingItems: buildInput(completedReport).pendingItems,
    } })
    selectTarget(first.result, REVIEW_TARGET_IDS.caseSummary)
    first.unmount()

    const reopenedInput = journeyInput()
    const reopened = renderHook(() => useGuidedReviewCards({
      ...reopenedInput,
      report: completedReport,
      fieldStates: { document_number: documentState },
      pendingItems: buildInput(completedReport).pendingItems,
    }))
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.caseSummary)
    act(() => reopened.result.current.returnToPreviousAction())
    expect(reopened.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.documentNumber)
    expect(reopened.result.current.currentAction?.title).toBe('请输入文号')
  })

  it('never persists temporary save recovery actions between user steps', () => {
    const failedSave = {
      ...journeyInput(),
      saveState: 'failed' as const,
      saveHasPending: true,
    }
    const view = renderHook(() => useGuidedReviewCards(failedSave))
    expect(view.result.current.currentAction?.kind).toBe('save_recovery')
    selectTarget(view.result, REVIEW_TARGET_IDS.documentNumber)
    act(() => view.result.current.selectAction('save-recovery'))
    view.unmount()

    expect(JSON.stringify(window.localStorage)).not.toContain('save-recovery')
  })

  it.each([
    ['invalid JSON', '{not-json'],
    ['an incompatible version', JSON.stringify({
      version: 999, caseId: 'SYNTHETIC-CASE-PERSISTENCE',
      entries: [{ actionId: 'pending-SYNTHETIC' }], index: 0,
    })],
    ['a mismatched case identity', JSON.stringify({
      version: 1, caseId: 'SYNTHETIC-OTHER-CASE',
      entries: [{ actionId: 'pending-SYNTHETIC' }], index: 0,
    })],
  ])('falls back safely for %s', (_label, storedValue) => {
    window.localStorage.setItem(
      guidedReviewNavigationStorageKey('SYNTHETIC-CASE-PERSISTENCE'),
      storedValue,
    )
    const view = renderHook(() => useGuidedReviewCards(journeyInput()))
    expect(view.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.documentNumber)
    expect(view.result.current.canReturnToPrevious).toBe(false)
  })

  it('falls back safely when browser storage is unavailable', () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('SYNTHETIC storage failure')
    })
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('SYNTHETIC storage failure')
    })
    try {
      const view = renderHook(() => useGuidedReviewCards(journeyInput()))
      expect(view.result.current.currentAction?.pendingItem?.targetId).toBe(REVIEW_TARGET_IDS.documentNumber)
      expect(view.result.current.canReturnToPrevious).toBe(false)
    } finally {
      getItem.mockRestore()
      setItem.mockRestore()
    }
  })
})
