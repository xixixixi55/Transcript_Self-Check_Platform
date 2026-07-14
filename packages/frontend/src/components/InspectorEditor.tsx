// Layer 11: FE_Components — 检查人员编辑器
import React from 'react'
import { Button, Space, Typography } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import type { Inspector } from '@biji/shared/types'
import EditableField from './EditableField'

const { Text } = Typography

interface Props {
  inspectors: Inspector[]
  onChange: (inspectors: Inspector[]) => void
}

export default function InspectorEditor({ inspectors, onChange }: Props) {
  const addInspector = () => {
    onChange([...inspectors, { name: '', unit: '', badge_number: '' }])
  }

  const updateInspector = (idx: number, field: string, value: string) => {
    const list = inspectors.map((ins, i) => i === idx ? { ...ins, [field]: value } : ins)
    onChange(list)
  }

  const removeInspector = (idx: number) => {
    onChange(inspectors.filter((_, i) => i !== idx))
  }

  return (
    <div>
      {inspectors.map((ins, idx) => (
        <div key={idx}
          style={{ border: '1px solid #f0f0f0', borderRadius: 6, padding: 12, marginBottom: 12, position: 'relative' }}>
          <Button type="text" danger size="small" icon={<DeleteOutlined />}
            style={{ position: 'absolute', top: 4, right: 4 }}
            onClick={() => removeInspector(idx)} />
          <Space direction="vertical" style={{ width: '100%' }}>
            <div><Text strong>姓名：</Text><EditableField type="text" placeholder="姓名" value={ins.name}
              onChange={value => updateInspector(idx, 'name', value)} /></div>
            <div><Text strong>单位：</Text><EditableField type="text" placeholder="单位" value={ins.unit}
              onChange={value => updateInspector(idx, 'unit', value)} /></div>
            <div><Text strong>警号：</Text><EditableField type="text" placeholder="警号" value={ins.badge_number}
              onChange={value => updateInspector(idx, 'badge_number', value)} /></div>
          </Space>
        </div>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={addInspector} block>添加检查人员</Button>
    </div>
  )
}
