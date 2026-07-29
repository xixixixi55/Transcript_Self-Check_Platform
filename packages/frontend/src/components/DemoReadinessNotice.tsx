import React from 'react'
import { Alert, List, Space, Tag, Typography } from 'antd'
import type { DemoReadinessItem, DemoReadinessState } from '@biji/shared/types'
import { useDemoReadiness } from '../hooks'

const { Text } = Typography
const statusPresentation: Record<
  DemoReadinessState, { text: string; color: string }
> = {
  ready: { text: '已就绪', color: 'success' },
  not_configured: { text: '未配置', color: 'default' },
  unavailable: { text: '当前不可用', color: 'error' },
  unknown: { text: '无法确认', color: 'warning' },
}

function ReadinessItem({ item }: { item: DemoReadinessItem }) {
  const presentation = statusPresentation[item.status]
  return (
    <List.Item>
      <Space direction="vertical" size={0}>
        <Space>
          <Text strong>{item.label}</Text>
          <Tag color={presentation.color}>{presentation.text}</Tag>
          {item.code && <Text code>{item.code}</Text>}
        </Space>
        <Text type="secondary">{item.guidance}</Text>
      </Space>
    </List.Item>
  )
}

export function DemoReadinessNotice() {
  const readiness = useDemoReadiness()
  return (
    <Alert
      type="info"
      showIcon
      message="Demo 环境就绪状态"
      description={readiness
        ? <List size="small" dataSource={readiness.items} renderItem={item => <ReadinessItem item={item} />} />
        : '正在读取后端的一次性就绪快照。'}
    />
  )
}
