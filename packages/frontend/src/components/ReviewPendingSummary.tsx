import React, { useMemo } from 'react'
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import {
  getReviewProgressSectionItems,
  REVIEW_PROGRESS_SECTIONS,
  type ReviewPendingItem,
} from '../hooks/useReviewChecklist'

interface ReviewPendingSummaryProps {
  items: ReviewPendingItem[]
  onNavigate: (item: ReviewPendingItem) => void
  onNavigateSection?: (sectionId: string) => void
  variant?: 'inline' | 'side'
}

export function ReviewPendingSummary({
  items,
  onNavigate,
  onNavigateSection,
  variant = 'inline',
}: ReviewPendingSummaryProps) {
  const [expanded, setExpanded] = React.useState(false)
  const [position, setPosition] = React.useState<{ left: number; top: number } | null>(null)
  const dockRef = React.useRef<HTMLElement>(null)
  const dragRef = React.useRef<{
    pointerId: number
    offsetX: number
    offsetY: number
    startX: number
    startY: number
    moved: boolean
  } | null>(null)
  const suppressTriggerClickRef = React.useRef(false)
  const sections = useMemo(() => REVIEW_PROGRESS_SECTIONS.map(section => {
    const sectionItems = getReviewProgressSectionItems(items, section.id)
    const requiredMissing = sectionItems.filter(item => item.kind === 'required_missing')
    const confirmations = sectionItems.filter(item => item.kind === 'confirmation_required')
    const validations = sectionItems.filter(item => item.kind === 'validation')
    return { ...section, items: sectionItems, requiredMissing, confirmations, validations }
  }), [items])
  const completedCount = sections.filter(section => section.requiredMissing.length === 0 && section.confirmations.length === 0).length
  const missingCount = sections.reduce((total, section) => total + section.requiredMissing.length, 0)
  const confirmationCount = sections.reduce((total, section) => total + section.confirmations.length, 0)
  const validationCount = sections.reduce((total, section) => total + section.validations.length, 0)
  const blockingCount = missingCount + confirmationCount

  const navigate = (item: ReviewPendingItem) => {
    onNavigate(item)
    if (variant === 'side') setExpanded(false)
  }

  const navigateSection = (sectionId: string) => {
    onNavigateSection?.(sectionId)
    if (variant === 'side') setExpanded(false)
  }

  const clampPosition = React.useCallback((left: number, top: number) => {
    const rect = dockRef.current?.getBoundingClientRect()
    const width = rect?.width || 40
    const height = rect?.height || 112
    const edge = 8
    const actionBarReserve = 88
    return {
      left: Math.min(Math.max(edge, left), Math.max(edge, window.innerWidth - width - edge)),
      top: Math.min(Math.max(edge, top), Math.max(edge, window.innerHeight - height - actionBarReserve)),
    }
  }, [])

  const startDragging = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (event.button > 0 || !dockRef.current) return
    const rect = dockRef.current.getBoundingClientRect()
    dragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    }
    setPosition(clampPosition(rect.left, rect.top))
    event.currentTarget.setPointerCapture?.(event.pointerId)
    event.preventDefault()
  }

  const moveDragging = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    if (!drag.moved && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < 4) return
    drag.moved = true
    setPosition(clampPosition(event.clientX - drag.offsetX, event.clientY - drag.offsetY))
  }

  const stopDragging = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return
    suppressTriggerClickRef.current = dragRef.current.moved
    dragRef.current = null
    event.currentTarget.releasePointerCapture?.(event.pointerId)
  }

  const resetPosition = () => setPosition(null)

  React.useLayoutEffect(() => {
    if (!position) return undefined
    const reclamp = () => setPosition(current => {
      if (!current) return current
      const next = clampPosition(current.left, current.top)
      return next.left === current.left && next.top === current.top ? current : next
    })
    reclamp()
    window.addEventListener('resize', reclamp)
    return () => window.removeEventListener('resize', reclamp)
  }, [clampPosition, expanded, items.length, position])

  const summary = (
    <section
      id={variant === 'side' ? 'review-pending-side-panel' : undefined}
      className={`review-pending-summary ${blockingCount === 0 ? 'review-pending-summary--complete' : 'review-pending-summary--has-items'} ${confirmationCount > 0 ? 'review-pending-summary--confirmation-pending' : ''}`}
      aria-label="审核进度与待核对项"
    >
      {variant === 'side' && (
        <div className="review-pending-dock__controls">
          <button type="button" className="review-pending-dock__reset" onClick={resetPosition}>重置位置</button>
          <button type="button" className="review-pending-dock__close" onClick={() => setExpanded(false)}>
            收起进度导航
          </button>
        </div>
      )}
      <div className="review-pending-summary__heading">
        {blockingCount === 0
          ? <CheckCircleOutlined aria-hidden="true" />
          : <WarningOutlined aria-hidden="true" />}
        <div>
          <strong>必填进度 {completedCount}/4</strong>
          <span>
            {missingCount > 0 ? `尚缺 ${missingCount} 个必填字段` : '四部分必填字段均已填写'}
            {confirmationCount > 0 ? `，另有 ${confirmationCount} 项完整性待确认` : ''}
            {validationCount > 0 ? `，另有 ${validationCount} 项校验提醒` : ''}
          </span>
        </div>
      </div>
      <div
        className={`review-progress__bar ${confirmationCount > 0 ? 'review-progress__bar--confirmation-pending' : ''}`}
        role="progressbar"
        aria-label="四部分必填进度"
        aria-valuemin={0}
        aria-valuemax={4}
        aria-valuenow={completedCount}
      >
        <span style={{ width: `${completedCount * 25}%` }} />
      </div>
      <div className="review-progress__sections">
        {sections.map(section => {
          const complete = section.requiredMissing.length === 0 && section.confirmations.length === 0
          const statusLabel = section.confirmations.length > 0
            ? `待确认 ${section.confirmations.length} 项`
            : complete ? '必填已齐' : `缺少 ${section.requiredMissing.length} 项`
          return (
            <div className={`review-progress__section ${complete ? 'review-progress__section--complete' : ''} ${section.confirmations.length > 0 ? 'review-progress__section--confirmation-pending' : ''}`} key={section.id}>
              <button
                type="button"
                className="review-progress__section-button"
                aria-label={`${section.label}，${statusLabel}`}
                onClick={() => navigateSection(section.id)}
              >
                <span className="review-progress__section-icon" aria-hidden="true">
                  {complete ? <CheckCircleOutlined /> : <WarningOutlined />}
                </span>
                <span className="review-progress__section-copy">
                  <strong>{section.label}</strong>
                  <span>{statusLabel}</span>
                </span>
                {section.validations.length > 0 && (
                  <span className="review-progress__validation-count">校验 {section.validations.length}</span>
                )}
              </button>
              {section.items.length > 0 && (
                <div className="review-pending-summary__items">
                  {section.items.map(item => (
                    <button
                      type="button"
                      className={`review-pending-summary__item ${item.kind === 'validation' || item.kind === 'confirmation_required' ? 'review-pending-summary__item--validation' : ''}`}
                      key={item.id}
                      onClick={() => navigate(item)}
                    >
                      {item.kind === 'validation' || item.kind === 'confirmation_required'
                        ? <ExclamationCircleOutlined aria-hidden="true" />
                        : <WarningOutlined aria-hidden="true" />}
                      <span>{item.fieldLabel}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )

  if (variant === 'inline') return summary

  return (
    <aside
      ref={dockRef}
      className={`review-pending-dock ${expanded ? 'review-pending-dock--expanded' : ''} ${blockingCount === 0 ? 'review-pending-dock--complete' : ''} ${confirmationCount > 0 ? 'review-pending-dock--confirmation-pending' : ''}`}
      style={position ? { left: position.left, top: position.top, right: 'auto', transform: 'none' } : undefined}
      aria-label="审核进度导航"
    >
      <button
        type="button"
        className="review-pending-dock__trigger"
        aria-label={`必填进度 ${completedCount}/4，待核对 ${items.length} 项`}
        aria-expanded={expanded}
        aria-controls="review-pending-side-panel"
        title="单击展开，按住拖动可移动"
        onPointerDown={startDragging}
        onPointerMove={moveDragging}
        onPointerUp={stopDragging}
        onPointerCancel={stopDragging}
        onClick={() => {
          if (suppressTriggerClickRef.current) {
            suppressTriggerClickRef.current = false
            return
          }
          setExpanded(value => !value)
        }}
      >
        {blockingCount === 0
          ? <CheckCircleOutlined aria-hidden="true" />
          : <WarningOutlined aria-hidden="true" />}
        <span>进度 {completedCount}/4</span>
      </button>
      {summary}
    </aside>
  )
}
