import React, { useMemo } from 'react'
import { ExclamationCircleOutlined, InfoCircleOutlined, WarningOutlined } from '@ant-design/icons'
import type { ReviewPendingItem } from '../hooks/useReviewChecklist'

interface ReviewPendingSummaryProps {
  items: ReviewPendingItem[]
  onNavigate: (item: ReviewPendingItem) => void
  variant?: 'inline' | 'side'
}

export function ReviewPendingSummary({ items, onNavigate, variant = 'inline' }: ReviewPendingSummaryProps) {
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
  const grouped = useMemo(() => {
    return items.reduce<Record<string, ReviewPendingItem[]>>((result, item) => {
      result[item.sectionLabel] = [...(result[item.sectionLabel] || []), item]
      return result
    }, {})
  }, [items])

  const navigate = (item: ReviewPendingItem) => {
    onNavigate(item)
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

  if (variant === 'side' && items.length === 0) return null

  const summary = (
    <section
      id={variant === 'side' ? 'review-pending-side-panel' : undefined}
      className={`review-pending-summary ${items.length ? 'review-pending-summary--has-items' : ''}`}
      aria-label="待核对摘要"
    >
      {variant === 'side' && (
        <div className="review-pending-dock__controls">
          <button type="button" className="review-pending-dock__reset" onClick={resetPosition}>重置位置</button>
          <button type="button" className="review-pending-dock__close" onClick={() => setExpanded(false)}>
            收起待核对项
          </button>
        </div>
      )}
      <div className="review-pending-summary__heading">
        {items.length ? <WarningOutlined aria-hidden="true" /> : <InfoCircleOutlined aria-hidden="true" />}
        <div>
          <strong>{items.length ? `基础待核对 ${items.length} 项` : '目前未发现可确定的待核对项'}</strong>
          <span>仅根据当前页面可识别的空缺字段和既有格式校验结果提示，不等同于完整业务审查。</span>
        </div>
      </div>
      {items.length > 0 && (
        <div className="review-pending-summary__groups">
          {Object.entries(grouped).map(([sectionLabel, sectionItems]) => (
            <div className="review-pending-summary__group" key={sectionLabel}>
              <span className="review-pending-summary__group-label">{sectionLabel} {sectionItems.length} 项</span>
              <div className="review-pending-summary__items">
                {sectionItems.map(item => (
                  <button
                    type="button"
                    className="review-pending-summary__item"
                    key={item.id}
                    onClick={() => navigate(item)}
                  >
                    {item.severity === 'error'
                      ? <ExclamationCircleOutlined aria-hidden="true" />
                      : <WarningOutlined aria-hidden="true" />}
                    <span>{item.fieldLabel}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )

  if (variant === 'inline') return summary

  return (
    <aside ref={dockRef} className={`review-pending-dock ${expanded ? 'review-pending-dock--expanded' : ''}`}
      style={position ? { left: position.left, top: position.top, right: 'auto', transform: 'none' } : undefined}
      aria-label="待核对导航">
      <button
        type="button"
        className="review-pending-dock__trigger"
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
        <WarningOutlined aria-hidden="true" />
        <span>待核对 {items.length}</span>
      </button>
      {summary}
    </aside>
  )
}
