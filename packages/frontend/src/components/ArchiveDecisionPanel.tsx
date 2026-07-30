// Layer 11: FE_Components — explicit post-parse compression decision.
import React from 'react'
import { Alert, Button, Space } from 'antd'
import type { CaseLifecycle } from '@biji/shared/types'

interface Props {
  lifecycle: CaseLifecycle
  busy?: boolean
  onImmediate: () => void
  onDeferred: () => void
}

export function ArchiveDecisionPanel({ lifecycle, busy = false, onImmediate, onDeferred }: Props) {
  if (lifecycle === 'review_ready') return (
    <Alert type="info" showIcon message="报告解析成功，请选择压缩时机。" action={<Space>
      <Button type="primary" loading={busy} onClick={onImmediate}>立即开始压缩</Button>
      <Button loading={busy} onClick={onDeferred}>稍后压缩</Button>
    </Space>} />
  )
  if (lifecycle === 'archive_deferred') return (
    <Alert type="warning" showIcon message="暂未压缩" description="案件和草稿已保留；以后可从案件操作区开始压缩。" action={<Button loading={busy} onClick={onImmediate}>立即开始压缩</Button>} />
  )
  if (lifecycle === 'archive_queued') return (
    <Alert
      type="info"
      showIcon
      message="已进入等待归档"
      description="后台任务将按资源准入和安全门控执行；请返回案件工作台查看阶段与活动摘要。"
    />
  )
  if (lifecycle === 'archive_interrupted') return (
    <Alert
      type="warning"
      showIcon
      message="上次压缩未完成"
      description="应用重启或执行中断导致上次压缩未完成；草稿仍可查看和编辑，半成品不会作为正式产物使用。"
      action={<Space>
        <Button type="primary" loading={busy} onClick={onImmediate}>重新确认并立即压缩</Button>
        <Button loading={busy} onClick={onDeferred}>稍后压缩</Button>
      </Space>}
    />
  )
  return null
}
