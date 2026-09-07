import { EditOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'
import type { GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'

interface Props {
  items: GuidedReviewHistoryItem[]
  onEditMaterial?: (targetId: string) => void
}

function HistoryFields({ fields }: { fields: NonNullable<GuidedReviewHistoryItem['fields']> }) {
  return (
    <dl className="guided-review-history__fields">
      {fields.map(field => (
        <div className="guided-review-history__field" key={field.label}>
          <dt>{field.label}：</dt>
          <dd>
            <span>{field.value}</span>
            {field.userProvided && <span className="guided-review-history__user-badge">
              {field.sourceLabel || '用户填写'}
            </span>}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function HistoryMaterial({ material, onEditMaterial }: {
  material: NonNullable<GuidedReviewHistoryItem['materials']>[number]
  onEditMaterial?: (targetId: string) => void
}) {
  const complete = material.photoCount >= material.requiredPhotoCount
  return (
    <div className={`guided-review-history__material guided-review-history__material--${material.imeiStatus}`}
      role="listitem" aria-label={material.label}>
      <div className="guided-review-history__material-heading">
        <span>
          {material.label}
          {material.userProvided && <span className="guided-review-history__user-badge">
            {material.sourceLabel || '用户填写'}
          </span>}
          {material.imeiStatus === 'attention' && (
            <span className="guided-review-history__attention-badge">IMEI 待核对</span>
          )}
        </span>
        <span className="guided-review-history__material-actions">
          <span
            className={`guided-review-history__material-count${complete
              ? ' guided-review-history__material-count--complete' : ''}`}
            aria-label={`${material.label}：已上传 ${material.photoCount} 张图片，共需 ${material.requiredPhotoCount} 张`}
          >
            {material.photoCount}/{material.requiredPhotoCount}
          </span>
          {material.targetId && onEditMaterial && (
            <Tooltip title={`修改${material.label}`}>
              <Button type="text" shape="circle" icon={<EditOutlined />}
                aria-label={`修改${material.label}`} onClick={() => onEditMaterial(material.targetId!)} />
            </Tooltip>
          )}
        </span>
      </div>
      {material.fields.length > 0 && <HistoryFields fields={material.fields} />}
    </div>
  )
}

function HistoryMaterials({ materials, onEditMaterial }: {
  materials: NonNullable<GuidedReviewHistoryItem['materials']>
  onEditMaterial?: (targetId: string) => void
}) {
  const completeMaterials = materials.filter(material => material.imeiStatus === 'complete')
  const attentionMaterials = materials.filter(material => material.imeiStatus !== 'complete')
  return (
    <div className="guided-review-history__materials" role="list" aria-label="检材与图片">
      {completeMaterials.length > 0 && (
        <details className="guided-review-history__material-group">
          <summary>IMEI 信息完整（{completeMaterials.length}项）</summary>
          <div className="guided-review-history__material-group-content" role="list">
            {completeMaterials.map(material => <HistoryMaterial key={material.id}
              material={material} onEditMaterial={onEditMaterial} />)}
          </div>
        </details>
      )}
      {attentionMaterials.map(material => <HistoryMaterial key={material.id}
        material={material} onEditMaterial={onEditMaterial} />)}
    </div>
  )
}

export function GuidedReviewHistory({ items, onEditMaterial }: Props) {
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
                  {item.materials && item.materials.length > 0 && (
                    <HistoryMaterials materials={item.materials} onEditMaterial={onEditMaterial} />
                  )}
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
