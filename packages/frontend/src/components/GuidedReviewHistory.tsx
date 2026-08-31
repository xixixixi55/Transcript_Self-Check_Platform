import {
  CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons'
import type { GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'

interface Props {
  items: GuidedReviewHistoryItem[]
}

function HistoryIcon({ tone }: { tone: GuidedReviewHistoryItem['tone'] }) {
  if (tone === 'complete' || tone === 'recovered') return <CheckCircleOutlined aria-hidden />
  if (tone === 'warning') return <ExclamationCircleOutlined aria-hidden />
  return <ClockCircleOutlined aria-hidden />
}

export function GuidedReviewHistory({ items }: Props) {
  return (
    <section className="guided-review-history" role="region" aria-labelledby="guided-review-history-title" tabIndex={0}>
      <div className="guided-review-history__heading">
        <div className="guided-review-history__summary">
          <h2 id="guided-review-history-title">历史预览</h2>
          <span>{items.length ? `处理轨迹 · ${items.length} 条事实` : '等待形成轨迹'}</span>
        </div>
      </div>
      <div className="guided-review-history__content">
        {items.length ? (
          <ol className="guided-review-history__list">
            {items.map(item => (
              <li className={`guided-review-history__item guided-review-history__item--${item.tone}`} key={item.id}>
                <span className="guided-review-history__icon"><HistoryIcon tone={item.tone} /></span>
                <div>
                  <h3>{item.title}</h3>
                  {item.detail && <p>{item.detail}</p>}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <div className="guided-review-history__empty">办理轨迹会随案件现有事实逐步形成。</div>
        )}
      </div>
    </section>
  )
}
