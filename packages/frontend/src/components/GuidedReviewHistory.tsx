import type { GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'

interface Props {
  items: GuidedReviewHistoryItem[]
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
          <h2 id="guided-review-history-title">Word 内容预览</h2>
          <span>{items.length ? '按文书结构汇总，供快速核对' : '暂无可预览内容'}</span>
        </div>
      </div>
      <div className="guided-review-history__content">
        {items.length ? (
          <ol className="guided-review-history__list">
            {items.map(item => (
              <li className={`guided-review-history__item guided-review-history__item--${item.tone}`} key={item.id}>
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
          <div className="guided-review-history__empty">请先完善笔录信息，内容会在这里同步更新。</div>
        )}
      </div>
    </section>
  )
}
