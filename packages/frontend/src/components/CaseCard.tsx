// Layer 11: FE_Components — one persistent case workbench card.
import React from 'react'
import { Button, Card, Space, Typography } from 'antd'
import { Link } from 'react-router-dom'
import type { CaseShell, TaskRecord } from '@biji/shared/types'
import { CaseStatusBadge } from './CaseStatusBadge'
import { SourceStatusBadge } from './SourceStatusBadge'

const { Text } = Typography

function displayDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN', { hour12: false })
}
interface Props {
  shell: CaseShell
  task?: TaskRecord
  sourceRequiresReselection?: boolean
  onRetry: () => void
  onCancel: () => void
  onDeleteCheck: () => void
  actionBusy?: boolean
}

export function CaseCard({ shell, task, sourceRequiresReselection, onRetry, onCancel, onDeleteCheck, actionBusy = false }: Props) {
  const reviewable = shell.report_available && shell.lifecycle !== 'parse_failed_retryable'
  const canRetry = task?.status === 'failed_retryable' || task?.status === 'interrupted'
  const canCancel = task?.status === 'queued' || task?.status === 'running'
  return (
    <Card className="case-workbench-card" title={shell.case_number || shell.case_name} extra={<CaseStatusBadge lifecycle={shell.lifecycle} task={task} />}>
      <div className="case-workbench-card__summary">{shell.case_summary || '暂无案件摘要'}</div>
      <div className="case-workbench-card__meta"><Text type="secondary">案件名称</Text><span>{shell.case_name || '未命名案件'}</span></div>
      <div className="case-workbench-card__meta"><Text type="secondary">当前阶段</Text><span>{task?.stage === 'parse' ? '报告解析' : task?.stage || '案件处理'}</span></div>
      <div className="case-workbench-card__meta"><Text type="secondary">任务进度</Text><span>{task?.percent == null ? '等待后端状态' : `${Math.round(task.percent)}%`}</span></div>
      <div className="case-workbench-card__meta"><Text type="secondary">创建时间</Text><span>{displayDate(shell.created_at)}</span></div>
      <div className="case-workbench-card__meta"><Text type="secondary">更新时间</Text><span>{displayDate(shell.updated_at)}</span></div>
      <Space wrap className="case-workbench-card__actions">
        {reviewable ? <Link to={`/electronic-inspection/cases/${encodeURIComponent(shell.case_id)}`}><Button type="primary">打开案件</Button></Link> : <Button disabled>等待解析完成</Button>}
        {sourceRequiresReselection && <SourceStatusBadge status="requires_reselection" />}
        {canRetry && <Button onClick={onRetry} loading={actionBusy}>重试解析</Button>}
        {canCancel && <Button danger onClick={onCancel} loading={actionBusy}>取消任务</Button>}
        <Button onClick={onDeleteCheck} disabled={actionBusy}>删除检查</Button>
      </Space>
    </Card>
  )
}
