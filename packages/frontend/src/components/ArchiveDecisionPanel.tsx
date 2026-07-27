// Layer 11: FE_Components — explicit post-parse compression decision.
import React from 'react'
import { Alert, Button, Space } from 'antd'
import type { CaseLifecycle } from '@biji/shared/types'

interface Props {
  lifecycle: CaseLifecycle
  busy?: boolean
  contextReady?: boolean
  onImmediate: () => void
  onDeferred: () => void
}

export function ArchiveDecisionPanel({ lifecycle, busy = false, contextReady = false, onImmediate, onDeferred }: Props) {
  if (lifecycle === 'review_ready') return (
    <Alert type="info" showIcon message="报告解析成功，请选择压缩时机。" action={<Space>
      <Button type="primary" loading={busy} onClick={onImmediate}>立即开始压缩</Button>
      <Button loading={busy} onClick={onDeferred}>稍后压缩</Button>
    </Space>} />
  )
  if (lifecycle === 'archive_deferred') return (
    <Alert type="warning" showIcon message="暂未压缩" description="案件和草稿已保留；以后可从案件操作区开始压缩。" action={<Button loading={busy} onClick={onImmediate}>立即开始压缩</Button>} />
  )
  if (lifecycle === 'archive_queued' && !contextReady) return (
    <Alert type="info" showIcon message="已选择立即压缩" description="将进入现有 Legacy 显式压缩入口，不显示虚假进度。" action={<Button loading={busy} onClick={onImmediate}>进入压缩入口</Button>} />
  )
  return null
}
