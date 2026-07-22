// Layer 11: FE_Components — 检材情况编辑器
import React from 'react'
import { Alert, Button, Select, Space, Typography } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import type { EvidenceItem } from '@biji/shared/types'
import EditableField from './EditableField'

const { Text } = Typography

const MATERIAL_TYPE_OPTIONS = [
  { label: '手机', value: 'phone' },
  { label: '平板', value: 'tablet' },
  { label: '待确认', value: 'unconfirmed' },
]

interface Props {
  items: EvidenceItem[]
  onChange: (items: EvidenceItem[]) => void
}

export default function EvidenceEditor({ items, onChange }: Props) {
  const addItem = () => {
    onChange([...items, {
      id: String(Date.now()),
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

  const updateMaterialType = (idx: number, value: 'phone' | 'tablet' | 'unconfirmed') => {
    onChange(items.map((item, i) => i === idx ? {
      ...item,
      material_type: value,
      material_type_status: value === 'unconfirmed' ? 'unconfirmed' : 'confirmed_by_user',
      material_type_source: 'user',
      material_type_diagnostic: undefined,
    } : item))
  }

  return (
    <div>
      {items.map((item, idx) => (
        <div key={item.id || idx}
          style={{ border: '1px solid #f0f0f0', borderRadius: 6, padding: 12, marginBottom: 12, position: 'relative' }}>
          <Button type="text" danger size="small" icon={<DeleteOutlined />}
            style={{ position: 'absolute', top: 4, right: 4 }}
            onClick={() => removeItem(idx)} />
          <Space direction="vertical" style={{ width: '100%' }}>
            <div><Text strong>设备名称：</Text><EditableField type="text"
              placeholder="如 HUAWEI HBN-AL00" value={item.device_name || item.model || item.device_type || ''}
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
            {item.material_type !== 'tablet' && <>
              <div><Text strong>IMEI1：</Text><EditableField type="text" value={item.imei1 || ''}
                onChange={value => updateItem(idx, 'imei1', value)} /></div>
              <div><Text strong>IMEI2：</Text><EditableField type="text" value={item.imei2 || ''}
                onChange={value => updateItem(idx, 'imei2', value)} /></div>
            </>}
            {item.material_type !== 'phone' && (
              <div><Text strong>序列号：</Text><EditableField type="text" value={item.serial_number || ''}
                onChange={value => updateItem(idx, 'serial_number', value)} /></div>
            )}
            <div><Text strong>检材编号：</Text><EditableField type="text"
              placeholder="如 SYN-JC00000001" value={item.evidence_number}
              onChange={value => updateItem(idx, 'evidence_number', value)} /></div>
          </Space>
        </div>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={addItem} block>添加检材</Button>
    </div>
  )
}
