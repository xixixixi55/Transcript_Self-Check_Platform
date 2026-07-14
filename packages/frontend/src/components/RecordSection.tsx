// Layer 11: FE_Components — 笔录章节卡片组件
import React from 'react'
import { Card, Typography } from 'antd'

const { Title } = Typography

interface Props {
  title: string
  children: React.ReactNode
  collapsible?: boolean
}

export default function RecordSection({ title, children, collapsible = true }: Props) {
  return (
    <Card
      title={<span style={{ fontWeight: 600 }}>{title}</span>}
      size="small"
      style={{ marginBottom: 16 }}
      styles={{ body: { padding: 16 } }}
    >
      {children}
    </Card>
  )
}
