// Layer 11: FE_Components — field source and pending state shown without exporting color to Word.
import React from 'react'
import { Space, Tag } from 'antd'
import type { FieldState } from '@biji/shared/types'

const SOURCE_LABELS = { report: '报告解析', user: '用户修改', system_default: '系统默认' } as const
const SOURCE_COLORS = { report: undefined, user: 'blue', system_default: 'default' } as const

export function FieldProvenanceBadge({ state }: { state?: FieldState }) {
  if (!state) return null
  return (
    <Space size={4} className="field-provenance-badge">
      <Tag color={SOURCE_COLORS[state.source]}>{SOURCE_LABELS[state.source]}</Tag>
      {state.confirmation === 'pending' && <Tag color="orange">待人工确认</Tag>}
    </Space>
  )
}
