import type { EvidenceItem } from '@biji/shared/types'
import { Select } from 'antd'
import { useState } from 'react'
import type { GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'
import EditableField from './EditableField'

type SaveState = 'idle' | 'saving' | 'saved' | 'failed' | 'conflict' | 'not_changed'

interface Props {
  items: GuidedReviewHistoryItem[]
  evidenceItems?: EvidenceItem[]
  onEvidenceItemsChange?: (items: EvidenceItem[]) => void
  readOnly?: boolean
  saveState?: SaveState
  saveHasPending?: boolean
}

const MATERIAL_TYPE_OPTIONS = [
  { label: '手机', value: 'phone' },
  { label: '平板', value: 'tablet' },
  { label: '待确认', value: 'unconfirmed' },
]

const EXTRACTABLE_OPTIONS = [
  { label: '可提取', value: 'true' },
  { label: '无法提取', value: 'false' },
]

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

function saveStatusText(saveState: SaveState | undefined, saveHasPending: boolean | undefined): string {
  if (saveState === 'failed') return '自动保存失败，当前输入仍保留'
  if (saveState === 'conflict') return '自动保存冲突，当前输入仍保留'
  if (saveState === 'saving' || saveHasPending) return '正在自动保存…'
  if (saveState === 'saved' || saveState === 'not_changed') return '已自动保存'
  return '修改后自动保存'
}

function displayDeviceName(item: EvidenceItem): string {
  const brand = item.brand?.trim() || ''
  const model = item.model?.trim() || ''
  if (brand && model) {
    return model.toLocaleLowerCase().includes(brand.toLocaleLowerCase()) ? model : `${brand} ${model}`
  }
  return item.device_name?.trim() || model || item.device_type?.trim() || ''
}

function MaterialField({ label, material, children }: {
  label: string
  material: NonNullable<GuidedReviewHistoryItem['materials']>[number]
  children: React.ReactNode
}) {
  const state = material.fields.find(field => field.label === label)
  return (
    <div className="guided-review-history__field">
      <dt>{label}：</dt>
      <dd>
        {children}
        {state?.userProvided && <span className="guided-review-history__user-badge">
          {state.sourceLabel || '用户填写'}
        </span>}
      </dd>
    </div>
  )
}

function EditableMaterialFields({ material, item, onChange }: {
  material: NonNullable<GuidedReviewHistoryItem['materials']>[number]
  item: EvidenceItem
  onChange: (item: EvidenceItem) => void
}) {
  const inferredExtractable = Boolean(item.imei1?.trim() || item.imei2?.trim())
  const extractable = typeof item.extractable === 'boolean' ? item.extractable : inferredExtractable
  const update = (values: Partial<EvidenceItem>) => onChange({ ...item, ...values })
  return (
    <dl className="guided-review-history__fields guided-review-history__fields--editable">
        <MaterialField label="设备" material={material}>
          <EditableField type="text" value={displayDeviceName(item)} placeholder="待填写"
            onChange={value => update({ device_name: value, brand: '', model: '' })} />
        </MaterialField>
        <MaterialField label="类型" material={material}>
          <Select aria-label={`${material.label}类型`} variant="borderless" size="small"
            value={item.material_type || 'unconfirmed'} options={MATERIAL_TYPE_OPTIONS}
            onChange={(value: 'phone' | 'tablet' | 'unconfirmed') => update({
              material_type: value,
              material_type_status: value === 'unconfirmed' ? 'unconfirmed' : 'confirmed_by_user',
              material_type_source: 'user', material_type_diagnostic: undefined,
            })} />
        </MaterialField>
        <MaterialField label="IMEI 1" material={material}>
          <EditableField type="text" value={item.imei1 || ''} placeholder="待核对"
            onChange={value => update({ imei1: value })} />
        </MaterialField>
        <MaterialField label="IMEI 2" material={material}>
          <EditableField type="text" value={item.imei2 || ''} placeholder="待核对"
            onChange={value => update({ imei2: value })} />
        </MaterialField>
        <MaterialField label="序列号" material={material}>
          <EditableField type="text" value={item.serial_number || ''} placeholder="未识别"
            onChange={value => update({ serial_number: value })} />
        </MaterialField>
        <MaterialField label="提取情况" material={material}>
          <Select aria-label={`${material.label}提取情况`} variant="borderless" size="small"
            value={String(extractable)} options={EXTRACTABLE_OPTIONS}
            onChange={value => update({ extractable: value === 'true' })} />
        </MaterialField>
        {!extractable && <MaterialField label="无法提取原因" material={material}>
          <EditableField type="textarea" value={item.unextractable_reason || ''} placeholder="请填写原因"
            onChange={value => update({ unextractable_reason: value })} />
        </MaterialField>}
    </dl>
  )
}

function HistoryMaterial({ material, evidenceItems, onEvidenceItemsChange, readOnly, saveState, saveHasPending }: {
  material: NonNullable<GuidedReviewHistoryItem['materials']>[number]
  evidenceItems?: EvidenceItem[]
  onEvidenceItemsChange?: (items: EvidenceItem[]) => void
  readOnly?: boolean
  saveState?: SaveState
  saveHasPending?: boolean
}) {
  const [hasEdited, setHasEdited] = useState(false)
  const complete = material.photoCount >= material.requiredPhotoCount
  const evidenceIndex = evidenceItems?.findIndex(item => (item.evidence_id || item.id) === material.id) ?? -1
  const editableItem = evidenceIndex >= 0 ? evidenceItems?.[evidenceIndex] : undefined
  const updateItem = (item: EvidenceItem) => {
    if (!onEvidenceItemsChange || !evidenceItems || readOnly) return
    setHasEdited(true)
    const next = [...evidenceItems]
    next[evidenceIndex] = item
    onEvidenceItemsChange(next)
  }
  return (
    <div className={`guided-review-history__material guided-review-history__material--${material.imeiStatus}`}
      role="listitem" aria-label={material.label}>
      <div className="guided-review-history__material-heading">
        <span>
          {editableItem && onEvidenceItemsChange && !readOnly ? <>
            {`检材 ${evidenceIndex + 1} · `}
            <EditableField type="text" value={editableItem.evidence_number || ''} placeholder="编号待填写"
              onChange={value => updateItem({ ...editableItem, evidence_number: value })} />
          </> : material.label}
          {material.userProvided && <span className="guided-review-history__user-badge">
            {material.sourceLabel || '用户填写'}
          </span>}
          {material.imeiStatus === 'attention' && <span className="guided-review-history__attention-badge">
            检材信息待核对
          </span>}
        </span>
        <span className={`guided-review-history__material-count${complete
          ? ' guided-review-history__material-count--complete' : ''}`}
          aria-label={`${material.label}：已上传 ${material.photoCount} 张图片，共需 ${material.requiredPhotoCount} 张`}>
          {material.photoCount}/{material.requiredPhotoCount}
        </span>
      </div>
      {editableItem && onEvidenceItemsChange && !readOnly
        ? <>
          <EditableMaterialFields material={material} item={editableItem} onChange={updateItem} />
          {hasEdited && <div
            className={`guided-review-history__save-state guided-review-history__save-state--${saveState || 'idle'}`}
            role="status" aria-live="polite">{saveStatusText(saveState, saveHasPending)}</div>}
        </>
        : material.fields.length > 0 && <HistoryFields fields={material.fields} />}
    </div>
  )
}

function HistoryMaterials({ materials, evidenceItems, onEvidenceItemsChange, readOnly, saveState, saveHasPending }: {
  materials: NonNullable<GuidedReviewHistoryItem['materials']>
  evidenceItems?: EvidenceItem[]
  onEvidenceItemsChange?: (items: EvidenceItem[]) => void
  readOnly?: boolean
  saveState?: SaveState
  saveHasPending?: boolean
}) {
  const renderMaterial = (material: NonNullable<GuidedReviewHistoryItem['materials']>[number]) => (
    <HistoryMaterial key={material.id} material={material} evidenceItems={evidenceItems}
      onEvidenceItemsChange={onEvidenceItemsChange} readOnly={readOnly}
      saveState={saveState} saveHasPending={saveHasPending} />
  )
  const completeMaterials = materials.filter(material => material.imeiStatus === 'complete')
  const attentionMaterials = materials.filter(material => material.imeiStatus !== 'complete')
  return (
    <div className="guided-review-history__materials" role="list" aria-label="检材与图片">
      {completeMaterials.length > 0 && <details className="guided-review-history__material-group">
        <summary>检材信息完整（{completeMaterials.length}项）</summary>
        <div className="guided-review-history__material-group-content" role="list">
          {completeMaterials.map(renderMaterial)}
        </div>
      </details>}
      {attentionMaterials.map(renderMaterial)}
    </div>
  )
}

export function GuidedReviewHistory({
  items, evidenceItems, onEvidenceItemsChange, readOnly, saveState, saveHasPending,
}: Props) {
  return (
    <section className="guided-review-history" role="region" aria-labelledby="guided-review-history-title" tabIndex={0}>
      <div className="guided-review-history__heading">
        <div className="guided-review-history__summary">
          <h2 id="guided-review-history-title">Word 内容预览</h2>
          <span>{items.length ? '按文书结构汇总，供快速核对' : '暂无可预览内容'}</span>
        </div>
      </div>
      <div className="guided-review-history__content">
        {items.length ? <ol className="guided-review-history__list">
          {items.map(item => <li className={`guided-review-history__item guided-review-history__item--${item.tone}`} key={item.id}>
            <div>
              <h3>{item.title}</h3>
              {item.detail && <p>{item.detail}</p>}
              {item.fields && item.fields.length > 0 && <HistoryFields fields={item.fields} />}
              {item.materials && item.materials.length > 0 && <HistoryMaterials materials={item.materials}
                evidenceItems={evidenceItems} onEvidenceItemsChange={onEvidenceItemsChange} readOnly={readOnly}
                saveState={saveState} saveHasPending={saveHasPending} />}
            </div>
          </li>)}
        </ol> : <div className="guided-review-history__empty">请先完善笔录信息，内容会在这里同步更新。</div>}
      </div>
    </section>
  )
}
