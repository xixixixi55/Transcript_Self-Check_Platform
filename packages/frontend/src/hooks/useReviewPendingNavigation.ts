import { useCallback, useEffect, useRef } from 'react'
import { REVIEW_REVEAL_TARGET_EVENT, type ReviewPendingItem } from './useReviewChecklist'

export function useReviewPendingNavigation() {
  const highlightTimer = useRef<number | null>(null)

  const navigateToPendingItem = useCallback((item: ReviewPendingItem) => {
    window.dispatchEvent(new CustomEvent(REVIEW_REVEAL_TARGET_EVENT, {
      detail: { sectionId: item.sectionId, targetId: item.targetId },
    }))
    window.setTimeout(() => {
      const target = document.getElementById(item.targetId) || document.getElementById(item.sectionId)
      if (!target) return
      target.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
      document.querySelector('.review-navigation-target--active')?.classList.remove('review-navigation-target--active')
      target.classList.add('review-navigation-target--active')
      const focusTarget = target.matches('input, textarea, select')
        ? target
        : target.querySelector<HTMLElement>('input, textarea, select')
          || (target.matches('[tabindex]') ? target : target.querySelector<HTMLElement>('[tabindex], button'))
      focusTarget?.focus({ preventScroll: true })
      if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current)
      highlightTimer.current = window.setTimeout(() => {
        target.classList.remove('review-navigation-target--active')
      }, 1800)
    }, 0)
  }, [])

  useEffect(() => () => {
    if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current)
  }, [])

  return navigateToPendingItem
}
