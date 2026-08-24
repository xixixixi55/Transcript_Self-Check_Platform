// Layer 11: FE_Components — 检材情况编辑器
import React from 'react'
import { Alert, Button, Card, Input, Select, Space, Typography } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import type { EvidenceItem, FieldState } from '@biji/shared/types'
import EditableField from './EditableField'
import { FieldProvenanceBadge } from './FieldProvenanceBadge'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

const { Text } = Typography

const MATERIAL_TYPE_OPTIONS = [
  { label: '手机', value: 'phone' },
  { label: '平板', value: 'tablet' },
  { label: '待确认', value: 'unconfirmed' },
]
const EXTRACTABLE_OPTIONS = [
  { label: '可以提取', value: 'true' },
  { label: '无法提取', value: 'false' },
]

interface Props {
  items: EvidenceItem[]
  fieldStates?: Record<string, FieldState>
  onChange: (items: EvidenceItem[]) => void
}

function displayDeviceName(item: EvidenceItem): string {
  const brand = String(item.brand || '').trim()
  const model = String(item.model || '').trim()
  if (brand && model) {
    if (model.toLocaleLowerCase().includes(brand.toLocaleLowerCase())) return model
    return `${brand} ${model}`
  }
  return item.device_name || model || item.device_type || ''
}

function evidenceState(item: EvidenceItem, fieldStates?: Record<string, FieldState>): FieldState | undefined {
  const identity = item.evidence_id || item.id
  if (!identity) return undefined
  return fieldStates?.[`evidence.${identity}.model`] || fieldStates?.[`evidence.${identity}.evidence_number`]
}

export default function EvidenceEditor({ items, fieldStates, onChange }: Props) {
  const [draggedIndex, setDraggedIndex] = React.useState<number | null>(null)
  const addItem = () => {
    const evidenceId = `local-evidence-${Date.now()}-${items.length + 1}`
    onChange([...items, {
      id: evidenceId,
      evidence_id: evidenceId,
      device_type: '',
      device_name: '',
      model: '',
      imei1: '',
      imei2: '',
      serial_number: '',
      evidence_number: '',
    }])
  }

  const updateItem = (idx: number, field: string, value: string) => {
    const list = items.map((item, i) => i === idx ? { ...item, [field]: value } : item)
    onChange(list)
  }

  const removeItem = (idx: number) => {
    onChange(items.filter((_, i) => i !== idx))
  }

  const moveItem = (from: number, to: number) => {
    if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return
    const next = [...items]
    const [item] = next.splice(from, 1)
    next.splice(to, 0, item)
    onChange(next)
  }

  const updateMaterialType = (idx: number, value: 'phone' | 'tablet' | 'unconfirmed') => {
    onChange(items.map((item, i) => i === idx ? {
      ...item,
      material_type: value,
      material_type_status: value === 'unconfirmed' ? 'unconfirmed' : 'confirmed_by_user',
      material_type_source: 'user',
      material_type_diagnostic: undefined,
    } : item))
  }

  const isExtractable = (item: EvidenceItem) => typeof item.extractable === 'boolean'
    ? item.extractable
    : Boolean(item.imei1?.trim() || item.imei2?.trim() || item.serial_number?.trim())

  return (
    <div>
      <Text type="secondary">可拖拽卡片调整检材顺序。</Text>
      {items.map((item, idx) => (
        <div id={REVIEW_TARGET_IDS.evidence(idx)} className="review-navigation-target" tabIndex={-1}
          key={item.evidence_id || item.id || idx} data-testid={`evidence-card-${idx}`} draggable
          onDragStart={() => setDraggedIndex(idx)}
          onDragOver={event => event.preventDefault()}
          onDrop={() => { if (draggedIndex !== null) moveItem(draggedIndex, idx); setDraggedIndex(null) }}
          onDragEnd={() => setDraggedIndex(null)}
          style={{ marginBottom: 12 }}>
        <Card size="small" title={`检材 ${idx + 1}`} extra={<FieldProvenanceBadge state={evidenceState(item, fieldStates)} />}>
          <Button type="text" danger size="small" icon={<DeleteOutlined />}
            onClick={() => removeItem(idx)} />
          <Space direction="vertical" style={{ width: '100%' }}>
            <div><Text strong>设备名称：</Text><EditableField type="text"
              placeholder="如 HUAWEI HBN-AL00" value={displayDeviceName(item)}
              onChange={value => updateItem(idx, 'device_name', value)} /></div>
            <div>
              <Text strong>检材类型：</Text>
              <Select
                aria-label={`检材${idx + 1}类型`}
                value={item.material_type || 'unconfirmed'}
                options={MATERIAL_TYPE_OPTIONS}
                onChange={(value: 'phone' | 'tablet' | 'unconfirmed') => updateMaterialType(idx, value)}
                style={{ minWidth: 140 }}
              />
              {item.material_type_status === 'confirmed_by_report' && (
                <Text type="secondary">（报告明确字段候选）</Text>
              )}
              {item.material_type_status === 'confirmed_by_user' && (
                <Text type="secondary">（用户已确认）</Text>
              )}
            </div>
            {(!item.material_type || item.material_type === 'unconfirmed' || item.material_type_status === 'unconfirmed') && (
              <Alert type="warning" showIcon message="请确认检材类型；未确认时不能导出。" />
            )}
            <div>
              <Text strong>是否可提取：</Text>
              <Select aria-label={`检材${idx + 1}是否可提取`}
                value={String(isExtractable(item))} options={EXTRACTABLE_OPTIONS}
                onChange={(value: string) => onChange(items.map((candidate, i) =>
                  i === idx ? { ...candidate, extractable: value === 'true' } : candidate))}
                style={{ minWidth: 140 }} />
              <Text type="secondary">（根据 IMEI 或序列号自动判断）</Text>
            </div>
            {!isExtractable(item) && (
              <div className="review-evidence-reason">
                <label htmlFor={`unextractable-reason-${idx}`}>
                  <Text strong>无法提取原因：</Text>
                </label>
                <Input.TextArea
                  id={`unextractable-reason-${idx}`}
                  aria-label={`检材${idx + 1}无法提取原因`}
                  aria-invalid={!item.unextractable_reason?.trim()}
                  value={item.unextractable_reason || ''}
                  placeholder="请填写无法提取原因，该内容将写入笔录"
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  maxLength={500}
                  status={item.unextractable_reason?.trim() ? undefined : 'error'}
                  onChange={event => updateItem(idx, 'unextractable_reason', event.target.value)}
                />
                {!item.unextractable_reason?.trim() && (
                  <Text type="danger" role="alert">请填写无法提取原因。</Text>
                )}
              </div>
            )}
            {isExtractable(item) && item.material_type !== 'tablet' && <>
              <div><Text strong>IMEI1：</Text><EditableField type="text" value={item.imei1 || ''}
                onChange={value => updateItem(idx, 'imei1', value)} /></div>
              <div><Text strong>IMEI2：</Text><EditableField type="text" value={item.imei2 || ''}
                onChange={value => updateItem(idx, 'imei2', value)} /></div>
            </>}
            {isExtractable(item) && item.material_type !== 'phone' && (
              <div><Text strong>序列号：</Text><EditableField type="text" value={item.serial_number || ''}
                onChange={value => updateItem(idx, 'serial_number', value)} /></div>
            )}
            <div><Text strong>检材编号：</Text><EditableField type="text"
              placeholder="如 SYN-JC00000001" value={item.evidence_number}
              onChange={value => updateItem(idx, 'evidence_number', value)} /></div>
          </Space>
        </Card>
        </div>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={addItem} block>添加检材</Button>
    </div>
  )
}
