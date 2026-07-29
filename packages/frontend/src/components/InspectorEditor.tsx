// Layer 11: FE_Components — 检查人员库多选和有序快照编辑器
import React from 'react'
import { Alert, Button, Card, Select, Space, Typography } from 'antd'
import { DeleteOutlined, DownOutlined, UpOutlined } from '@ant-design/icons'
import type { FieldState, InspectorLibraryRecord, InspectorSnapshot } from '@biji/shared/types'
import { FieldProvenanceBadge } from './FieldProvenanceBadge'

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
  const selectedIds = snapshots
    .map(snapshot => snapshot.inspector_id)
    .filter((id): id is string => Boolean(id))

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

  const move = (index: number, offset: number) => {
    const target = index + offset
    if (target < 0 || target >= snapshots.length) return
    const next = [...snapshots]
    const [item] = next.splice(index, 1)
    next.splice(target, 0, item)
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

  return (
    <div className="inspector-selector">
      {error && <Alert type="error" showIcon message={error} />}
      <Select
        mode="multiple"
        aria-label="选择检查人员"
        value={selectedIds}
        loading={loading}
        disabled={loading || Boolean(error)}
        placeholder={loading ? '正在加载启用人员…' : '请选择启用人员'}
        options={availableInspectors.map(record => ({
          label: `${record.name}｜${record.unit}｜${record.police_number}`,
          value: record.id,
        }))}
        onChange={handleSelect}
        style={{ width: '100%' }}
      />
      {!loading && !error && availableInspectors.length === 0 && (
        <Text type="secondary">暂无可选择的启用人员，请先在检查人员管理中添加或启用人员。</Text>
      )}
      <div className="inspector-selector__selected" aria-label="已选择检查人员">
        {snapshots.length > 0 && <Text type="secondary">可拖拽卡片调整检查人员顺序。</Text>}
        {snapshots.map((snapshot, index) => (
          <div className="inspector-selector__item" key={`${snapshot.snapshot_id || snapshot.inspector_id || 'legacy'}-${index}`}
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
              <Button aria-label={`上移${index + 1}`} icon={<UpOutlined />} disabled={index === 0} onClick={() => move(index, -1)} />
              <Button aria-label={`下移${index + 1}`} icon={<DownOutlined />} disabled={index === snapshots.length - 1} onClick={() => move(index, 1)} />
              <Button aria-label={`移除${index + 1}`} danger icon={<DeleteOutlined />} onClick={() => remove(index)} />
            </Space>
          </Card>
          </div>
        ))}
      </div>
      {snapshots.length === 0 && !loading && !error && <Text type="secondary">当前报告尚未选择检查人员，可选择任意数量。</Text>}
    </div>
  )
}
