// Layer 11: FE_Components — reusable opaque source accessibility status.
import React from 'react'
import { Tag } from 'antd'
import type { SourceAccessStatus } from '@biji/shared/types'

const LABELS: Record<SourceAccessStatus, string> = {
  pending: '来源待复核', available: '来源可用', invalid: '来源已失效', requires_reselection: '请重新选择来源',
}
export function SourceStatusBadge({ status }: { status: SourceAccessStatus }) {
  const color = status === 'available' ? 'green' : status === 'requires_reselection' || status === 'invalid' ? 'orange' : 'blue'
  return <Tag color={color}>{LABELS[status]}</Tag>
}
