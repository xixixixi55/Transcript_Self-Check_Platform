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

function HistoryFields({ fields }: { fields: NonNullable<GuidedReviewHistoryItem['fields']> }) {
  return (
    <dl className="guided-review-history__fields">
      {fields.map(field => (
        <div className="guided-review-history__field" key={field.label}>
          <dt>{field.label}：</dt>
          <dd>
            <span>{field.value}</span>
            {field.userProvided && <span className="guided-review-history__user-badge">用户填写</span>}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function HistoryMaterials({ materials }: { materials: NonNullable<GuidedReviewHistoryItem['materials']> }) {
  return (
    <div className="guided-review-history__materials" role="list" aria-label="检材与图片">
      {materials.map(material => {
        const complete = material.photoCount >= material.requiredPhotoCount
        return (
          <div className="guided-review-history__material" role="listitem" key={material.id}>
            <div className="guided-review-history__material-heading">
              <span>
                {material.label}
                {material.userProvided && <span className="guided-review-history__user-badge">用户填写</span>}
              </span>
              <span
                className={`guided-review-history__material-count${complete
                  ? ' guided-review-history__material-count--complete' : ''}`}
                aria-label={`${material.label}：已上传 ${material.photoCount} 张图片，共需 ${material.requiredPhotoCount} 张`}
              >
                {material.photoCount}/{material.requiredPhotoCount}
              </span>
            </div>
            {material.fields.length > 0 && <HistoryFields fields={material.fields} />}
          </div>
        )
      })}
    </div>
  )
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
                  {item.fields && item.fields.length > 0 && <HistoryFields fields={item.fields} />}
                  {item.materials && item.materials.length > 0 && <HistoryMaterials materials={item.materials} />}
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
