import React, { useMemo } from 'react'
import { ExclamationCircleOutlined, InfoCircleOutlined, WarningOutlined } from '@ant-design/icons'
import type { ReviewPendingItem } from '../hooks/useReviewChecklist'

interface ReviewPendingSummaryProps {
  items: ReviewPendingItem[]
  onNavigate: (sectionId: string) => void
}

export function ReviewPendingSummary({ items, onNavigate }: ReviewPendingSummaryProps) {
  const grouped = useMemo(() => {
    return items.reduce<Record<string, ReviewPendingItem[]>>((result, item) => {
      result[item.sectionLabel] = [...(result[item.sectionLabel] || []), item]
      return result
    }, {})
  }, [items])

  return (
    <section className={`review-pending-summary ${items.length ? 'review-pending-summary--has-items' : ''}`} aria-label="待核对摘要">
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
                    onClick={() => onNavigate(item.sectionId)}
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
}
