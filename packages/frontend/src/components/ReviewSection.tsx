import React, { useEffect, useId, useState } from 'react'
import { REVIEW_REVEAL_TARGET_EVENT } from '../hooks/useReviewChecklist'

interface ReviewSectionProps {
  id: string
  title: string
  pendingCount?: number
  defaultOpen?: boolean
  children: React.ReactNode
}

export function ReviewSection({ id, title, pendingCount = 0, defaultOpen = true, children }: ReviewSectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  const contentId = useId()

  useEffect(() => {
    const reveal = (event: Event) => {
      const detail = (event as CustomEvent<{ sectionId?: string }>).detail
      if (detail?.sectionId === id) setOpen(true)
    }
    window.addEventListener(REVIEW_REVEAL_TARGET_EVENT, reveal)
    return () => window.removeEventListener(REVIEW_REVEAL_TARGET_EVENT, reveal)
  }, [id])

  return (
    <section id={id} className="review-section" data-open={open}>
      <button
        type="button"
        className="review-section__header"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen(value => !value)}
      >
        <span className="review-section__chevron" aria-hidden="true">{open ? '⌄' : '›'}</span>
        <span className="review-section__title">{title}</span>
        {pendingCount > 0 && <span className="review-section__count">基础待核对 {pendingCount} 项</span>}
      </button>
      {open && <div id={contentId} className="review-section__body">{children}</div>}
    </section>
  )
}
