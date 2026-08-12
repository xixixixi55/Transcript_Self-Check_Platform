// Layer 11: FE_Components — 检查人员库多选和有序快照编辑器
import React from 'react'
import { Alert, Button, Card, Modal, Space, Typography } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import type { FieldState, InspectorLibraryRecord, InspectorSnapshot } from '@biji/shared/types'
import { FieldProvenanceBadge } from './FieldProvenanceBadge'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

const { Text } = Typography

interface Props {
  snapshots: InspectorSnapshot[]
  availableInspectors: InspectorLibraryRecord[]
  loading?: boolean
  error?: string | null
  fieldStates?: Record<string, FieldState>
  onChange: (snapshots: InspectorSnapshot[]) => void
}

function normalizeOrder(snapshots: InspectorSnapshot[]): InspectorSnapshot[] {
  return snapshots.map((snapshot, index) => ({ ...snapshot, selected_order: index }))
}

function snapshotFromRecord(record: InspectorLibraryRecord): InspectorSnapshot {
  return {
    inspector_id: record.id,
    name: record.name,
    unit: record.unit,
    police_number: record.police_number,
  }
}

function inspectorState(snapshot: InspectorSnapshot, fieldStates?: Record<string, FieldState>): FieldState | undefined {
  const identity = snapshot.snapshot_id || snapshot.inspector_id
  if (!identity) return fieldStates?.['introduction.inspectors']
  return fieldStates?.[`inspectors.${identity}.police_number`] || fieldStates?.[`inspectors.${identity}.name`]
}

export default function InspectorEditor({
  snapshots,
  availableInspectors,
  loading = false,
  error = null,
  fieldStates,
  onChange,
}: Props) {
  const [draggedIndex, setDraggedIndex] = React.useState<number | null>(null)
  const [pickerOpen, setPickerOpen] = React.useState(false)
  const selectedIds = snapshots
    .map(snapshot => snapshot.inspector_id)
    .filter((id): id is string => Boolean(id))
  const addableInspectors = availableInspectors.filter(record => !selectedIds.includes(record.id))
  const pickerDisabled = loading || Boolean(error) || addableInspectors.length === 0

  const handleSelect = (ids: string[]) => {
    const existing = new Map<string, InspectorSnapshot>()
    snapshots.forEach(snapshot => {
      if (snapshot.inspector_id) existing.set(snapshot.inspector_id, snapshot)
    })
    const records = new Map<string, InspectorLibraryRecord>(availableInspectors.map(record => [record.id, record]))
    const unavailableSelectedIds = snapshots.flatMap(snapshot => {
      const id = snapshot.inspector_id
      return id && !records.has(id) ? [id] : []
    })
    const selectedIds: string[] = [...unavailableSelectedIds, ...ids]
    const next = [...new Set(selectedIds)].map(id => {
      const existingSnapshot = existing.get(id)
      if (existingSnapshot) return existingSnapshot
      const record = records.get(id)
      return record ? snapshotFromRecord(record) : null
    })
      .filter((snapshot): snapshot is InspectorSnapshot => Boolean(snapshot))
    onChange(normalizeOrder(next))
  }

  const remove = (index: number) => {
    onChange(normalizeOrder(snapshots.filter((_, itemIndex) => itemIndex !== index)))
  }

  const moveTo = (from: number, to: number) => {
    if (from === to || from < 0 || to < 0 || from >= snapshots.length || to >= snapshots.length) return
    const next = [...snapshots]
    const [snapshot] = next.splice(from, 1)
    next.splice(to, 0, snapshot)
    onChange(normalizeOrder(next))
  }

  const openPicker = () => {
    if (pickerDisabled) return
    setPickerOpen(true)
  }

  const closePicker = () => {
    setPickerOpen(false)
  }

  const addInspector = (id: string) => {
    handleSelect([...selectedIds, id])
    closePicker()
  }

  return (
    <div className="inspector-selector">
      {error && <Alert type="error" showIcon message={error} />}
      {!loading && !error && availableInspectors.length === 0 && (
        <Text type="secondary">暂无可选择的启用人员，请先在检查人员管理中添加或启用人员。</Text>
      )}
      <div className="inspector-selector__selected" role="list" aria-label="已选择检查人员，可拖拽卡片调整顺序">
        {snapshots.length > 0 && <Text className="inspector-selector__hint" type="secondary">可拖拽卡片调整检查人员顺序。</Text>}
        {snapshots.map((snapshot, index) => (
          <div id={REVIEW_TARGET_IDS.inspector(index)} className="inspector-selector__item review-navigation-target" tabIndex={-1}
            key={`${snapshot.snapshot_id || snapshot.inspector_id || 'legacy'}-${index}`}
            role="listitem" aria-label={`检查人员 ${index + 1}，可拖拽调整顺序`}
            aria-grabbed={draggedIndex === index ? 'true' : 'false'}
            data-testid={`inspector-card-${index}`} draggable
            onDragStart={() => setDraggedIndex(index)}
            onDragOver={event => event.preventDefault()}
            onDrop={() => { if (draggedIndex !== null) moveTo(draggedIndex, index); setDraggedIndex(null) }}
            onDragEnd={() => setDraggedIndex(null)}>
            <Card size="small" title={`检查人员 ${index + 1}`} extra={<FieldProvenanceBadge state={inspectorState(snapshot, fieldStates)} />}>
              <Space direction="vertical" size={0}>
                <Text>{snapshot.name}</Text>
                <Text type="secondary">单位：{snapshot.unit}</Text>
                <Text type="secondary">警号：{snapshot.police_number}</Text>
              </Space>
              <Space>
                <Button aria-label={`移除${index + 1}`} danger icon={<DeleteOutlined />} onClick={() => remove(index)} />
              </Space>
            </Card>
          </div>
        ))}
        <div className="inspector-selector__item inspector-selector__item--add" role="listitem" data-testid="inspector-add-card">
          <button type="button" className="inspector-selector__add-card" aria-label="添加检查人员"
            disabled={pickerDisabled} onClick={openPicker}>
            <PlusOutlined />
            <span>添加检查人员</span>
          </button>
        </div>
      </div>
      {snapshots.length === 0 && !loading && !error && availableInspectors.length > 0 && (
        <Text className="inspector-selector__empty" type="secondary">点击加号卡片添加检查人员。</Text>
      )}
      <Modal title="添加检查人员" open={pickerOpen} onCancel={closePicker} footer={null}>
        <div className="inspector-picker" role="list" aria-label="未添加检查人员">
          {addableInspectors.map(record => (
            <button
              key={record.id}
              type="button"
              className="inspector-picker__option"
              data-testid={`inspector-option-${record.id}`}
              aria-label={`添加${record.name}`}
              onClick={() => addInspector(record.id)}
            >
              <strong>{record.name}</strong>
              <span>单位：{record.unit}</span>
              <span>警号：{record.police_number}</span>
            </button>
          ))}
        </div>
      </Modal>
    </div>
  )
}
