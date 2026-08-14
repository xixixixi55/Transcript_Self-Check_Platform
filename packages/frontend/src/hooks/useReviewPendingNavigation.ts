import { useCallback, useEffect, useRef } from 'react'
import { REVIEW_REVEAL_TARGET_EVENT, type ReviewPendingItem } from './useReviewChecklist'

export function useReviewPendingNavigation() {
  const highlightTimer = useRef<number | null>(null)

  const navigateToTarget = useCallback((sectionId: string, targetId: string) => {
    window.dispatchEvent(new CustomEvent(REVIEW_REVEAL_TARGET_EVENT, {
      detail: { sectionId, targetId },
    }))
    window.setTimeout(() => {
      const target = document.getElementById(targetId) || document.getElementById(sectionId)
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

  const navigateToPendingItem = useCallback((item: ReviewPendingItem) => {
    navigateToTarget(item.sectionId, item.targetId)
  }, [navigateToTarget])

  const navigateToSection = useCallback((sectionId: string) => {
    navigateToTarget(sectionId, sectionId)
  }, [navigateToTarget])

  useEffect(() => () => {
    if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current)
  }, [])

  return { navigateToPendingItem, navigateToSection }
}
