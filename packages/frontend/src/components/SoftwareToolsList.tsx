// Layer 11: FE_Components — 软件工具列表
// REQ-017: 展示软件工具列表，名称和版本号均可编辑
import React from 'react'
import { Button, Space } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import EditableField from './EditableField'
import type { SoftwareItem } from '@biji/shared/types'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

interface Props {
  tools: SoftwareItem[]
  onChange: (tools: SoftwareItem[]) => void
  readOnly?: boolean
}

export default function SoftwareToolsList({ tools, onChange, readOnly = false }: Props) {
  const update = (idx: number, field: keyof SoftwareItem, val: string) => {
    onChange(tools.map((t, i) => i === idx ? { ...t, [field]: val } : t))
  }

  const add = () => onChange([...tools, { name: '', version: '' }])
  const remove = (idx: number) => onChange(tools.filter((_, i) => i !== idx))

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={4}>
      {tools.map((tool, idx) => (
        <div id={REVIEW_TARGET_IDS.softwareTool(idx)} className="review-navigation-target" tabIndex={-1}
          key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <EditableField type="text" value={tool.name}
            onChange={v => update(idx, 'name', v)}
            placeholder="软件名称" />
          <span>版本号：</span>
          <EditableField type="text" value={tool.version}
            onChange={v => update(idx, 'version', v)}
            placeholder="版本号" />
          <Button type="text" danger size="small" icon={<DeleteOutlined />}
            onClick={() => remove(idx)} />
        </div>
      ))}
      {!readOnly && <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={add}>
        添加软件工具
      </Button>}
    </Space>
  )
}
