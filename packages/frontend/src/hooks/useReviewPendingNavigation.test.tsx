import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { REVIEW_TARGET_IDS, type ReviewPendingItem } from './useReviewChecklist'
import { useReviewPendingNavigation } from './useReviewPendingNavigation'

const discItem: ReviewPendingItem = {
  id: 'disc', sectionId: 'attachments', targetId: REVIEW_TARGET_IDS.discNumber,
  sectionLabel: '附件', fieldLabel: '光盘编号', reason: '为空', severity: 'warning',
}

describe('useReviewPendingNavigation', () => {
  afterEach(() => { vi.useRealTimers(); document.body.replaceChildren() })

  it('将光盘编号精确定位并聚焦到顶部输入框', () => {
    vi.useFakeTimers()
    const input = document.createElement('input')
    input.id = REVIEW_TARGET_IDS.discNumber
    input.scrollIntoView = vi.fn()
    document.body.append(input)
    const { result } = renderHook(() => useReviewPendingNavigation())
    act(() => { result.current(discItem); vi.advanceTimersByTime(0) })
    expect(input.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    expect(document.activeElement).toBe(input)
    expect(input.classList.contains('review-navigation-target--active')).toBe(true)
  })

  it('字段目标不存在时安全回退到章节', () => {
    vi.useFakeTimers()
    const section = document.createElement('section')
    section.id = discItem.sectionId
    section.tabIndex = -1
    section.scrollIntoView = vi.fn()
    document.body.append(section)
    const { result } = renderHook(() => useReviewPendingNavigation())
    act(() => { result.current({ ...discItem, targetId: 'missing' }); vi.advanceTimersByTime(0) })
    expect(section.scrollIntoView).toHaveBeenCalled()
    expect(document.activeElement).toBe(section)
  })
})
