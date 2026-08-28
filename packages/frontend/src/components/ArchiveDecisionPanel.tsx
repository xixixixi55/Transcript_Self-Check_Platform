// 第 11 层：FE_Components — 解析完成后的显式压缩决策。
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
      type="warning"
      showIcon
      message="已进入等待归档"
      description="后台任务将直接读取源报告目录。压缩完成前，请勿修改、移动或删除源文件，也不要继续使用取证软件向该目录写入数据。"
    />
  )
  if (lifecycle === 'archiving') return (
    <Alert
      type="warning"
      showIcon
      message="正在读取源文件并压缩"
      description="请勿修改、移动或删除源报告目录，也不要继续向该目录写入数据。系统会校验 RAR 完整性、分卷、MD5 和清单，但不会为源目录执行额外的重复全量扫描。"
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
