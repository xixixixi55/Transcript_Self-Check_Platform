// Layer 11: FE_Components — review source legend; color is supplementary only.
import React from 'react'
import { Space, Tag, Typography } from 'antd'
import type { FieldSource } from '@biji/shared/types'
import { getFieldSourceLabel } from '@biji/shared/utils'

const SOURCE_COLORS: Record<FieldSource, string | undefined> = {
  report: undefined,
  user: 'blue',
  system_default: 'default',
}

const SOURCES: FieldSource[] = ['report', 'user', 'system_default']

export function ReviewSourceLegend() {
  return (
    <div className="review-source-legend" aria-label="字段来源说明">
      <Space wrap size={8}>
        <Typography.Text type="secondary">字段来源：</Typography.Text>
        {SOURCES.map(source => <Tag key={source} color={SOURCE_COLORS[source]}>{getFieldSourceLabel(source)}</Tag>)}
        <Tag color="orange">待人工确认</Tag>
        <Typography.Text type="secondary">待确认状态始终以文字提示，不会写入 Word。</Typography.Text>
      </Space>
    </div>
  )
}
