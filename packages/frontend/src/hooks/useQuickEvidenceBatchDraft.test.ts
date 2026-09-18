import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  quickEvidenceBatchDraftStorageKey,
  useQuickEvidenceBatchDraft,
} from './useQuickEvidenceBatchDraft'

beforeEach(() => window.localStorage.clear())

describe('quick evidence batch draft persistence', () => {
  it('restores one case without leaking the draft into another case and clears it explicitly', () => {
    const view = renderHook(({ caseId }) => useQuickEvidenceBatchDraft(caseId), {
      initialProps: { caseId: 'SYNTHETIC-CASE-A' },
    })

    act(() => view.result.current.setValue('SYNTHETIC 手机一部（SYNTHETIC/TEST）SYN-JC01'))
    expect(window.localStorage.getItem(quickEvidenceBatchDraftStorageKey('SYNTHETIC-CASE-A')))
      .toContain('SYN-JC01')

    view.rerender({ caseId: 'SYNTHETIC-CASE-B' })
    expect(view.result.current.value).toBe('')
    view.rerender({ caseId: 'SYNTHETIC-CASE-A' })
    expect(view.result.current.value).toContain('SYN-JC01')

    act(() => view.result.current.clear())
    expect(view.result.current.value).toBe('')
    expect(window.localStorage.getItem(quickEvidenceBatchDraftStorageKey('SYNTHETIC-CASE-A'))).toBeNull()
  })

  it('ignores malformed or oversized stored values and does not fail when storage is unavailable', () => {
    window.localStorage.setItem(quickEvidenceBatchDraftStorageKey('SYNTHETIC-INVALID'), '{bad-json')
    window.localStorage.setItem(quickEvidenceBatchDraftStorageKey('SYNTHETIC-OVERSIZED'), JSON.stringify({
      version: 1, caseId: 'SYNTHETIC-OVERSIZED', value: 'x'.repeat(5001),
    }))

    const invalid = renderHook(() => useQuickEvidenceBatchDraft('SYNTHETIC-INVALID'))
    const oversized = renderHook(() => useQuickEvidenceBatchDraft('SYNTHETIC-OVERSIZED'))
    expect(invalid.result.current.value).toBe('')
    expect(oversized.result.current.value).toBe('')

    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementationOnce(() => {
      throw new Error('SYNTHETIC/TEST storage unavailable')
    })
    expect(() => act(() => invalid.result.current.setValue('SYNTHETIC-DRAFT'))).not.toThrow()
    expect(invalid.result.current.value).toBe('SYNTHETIC-DRAFT')
    setItem.mockRestore()
  })
})
