// Layer 11: FE_Components — one persistent case workbench card.
import React from 'react'
import { Button, Card, Dropdown, Space, Typography } from 'antd'
import { MoreOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import type { ArchiveCompletionStatus, ArchiveTaskAction, ArchiveTaskCardSummary, CaseShell, TaskRecord } from '@biji/shared/types'
import { CaseStatusBadge } from './CaseStatusBadge'
import { SourceStatusBadge } from './SourceStatusBadge'
import { ArchiveStatusPanel } from './ArchiveStatusPanel'

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
  onDelete: () => void
  archiveSummary?: ArchiveTaskCardSummary
  onArchiveAction?: (action: ArchiveTaskAction) => void
  onArchivePrecheck?: () => void
  actionBusy?: boolean
  completionStatus?: ArchiveCompletionStatus
  onThoroughDelete?: () => void
  onExport?: () => void
  exporting?: boolean
}

const COMPLETION_LABELS: Record<ArchiveCompletionStatus, { label: string; danger?: boolean }> = {
  compressing: { label: '压缩中' },
  disc_pending: { label: '待补盘号' },
  archive_complete: { label: '归档完成' },
  exported: { label: '已导出' },
}

const ACTION_LABELS: Record<ArchiveTaskAction, string> = {
  cancel: '取消归档',
  retry: '重试归档',
  view_result: '查看结果',
  view_details: '查看详情',
}

function primaryArchiveAction(summary?: ArchiveTaskCardSummary): ArchiveTaskAction | undefined {
  if (!summary) return undefined
  return (['retry', 'cancel', 'view_details'] as const)
    .find(action => summary.allowed_actions.includes(action))
}

function archiveActionLabel(action: ArchiveTaskAction, summary: ArchiveTaskCardSummary): string {
  if (action === 'view_details' && summary.status.includes('failed')) return '查看原因'
  if (action === 'retry' && summary.status === 'cancelled') return '重新归档'
  return ACTION_LABELS[action]
}

export function CaseCard({
  shell, task, archiveSummary, sourceRequiresReselection, onRetry, onCancel,
  onDelete, onArchiveAction, onArchivePrecheck, actionBusy = false,
  completionStatus, onThoroughDelete, onExport, exporting = false,
}: Props) {
  const reviewable = shell.report_available && shell.lifecycle !== 'parse_failed_retryable'
  const canRetry = task?.status === 'failed_retryable' || task?.status === 'interrupted'
  const canCancel = task?.status === 'queued' || task?.status === 'running'
  const archiveAction = primaryArchiveAction(archiveSummary)
  const exportReady = completionStatus === 'archive_complete' || completionStatus === 'exported'
  const secondaryArchiveActions = archiveSummary?.allowed_actions
    .filter(action => action !== archiveAction && action !== 'view_result') ?? []
  const menuItems = [
    ...secondaryArchiveActions.map(action => ({
      key: action,
      label: archiveSummary ? archiveActionLabel(action, archiveSummary) : ACTION_LABELS[action],
      onClick: () => onArchiveAction?.(action),
    })),
    { key: 'delete', label: '删除', onClick: onDelete },
    ...(completionStatus === 'exported' && onThoroughDelete
      ? [{ key: 'thorough-delete', label: '彻底删除', danger: true, onClick: onThoroughDelete }]
      : []),
  ]
  return (
    <Card
      className="case-workbench-card"
      title={<span className="case-workbench-card__title" title={shell.case_number || shell.case_name}>{shell.case_number || shell.case_name}</span>}
      extra={<CaseStatusBadge lifecycle={shell.lifecycle} task={task} />}
    >
      <div className="case-workbench-card__summary">{shell.case_summary || '暂无案件摘要'}</div>
      <div className="case-workbench-card__meta"><Text type="secondary">案件名称</Text><span>{shell.case_name || '未命名案件'}</span></div>
      <div className="case-workbench-card__meta"><Text type="secondary">更新时间</Text><span>{displayDate(shell.updated_at)}</span></div>
      <ArchiveStatusPanel summary={archiveSummary} />
      {completionStatus && (
        <div className="case-workbench-card__completion">
          <Text type={completionStatus === 'exported' ? 'success' : 'secondary'}>
            归档状态：{COMPLETION_LABELS[completionStatus].label}
          </Text>
        </div>
      )}
      <Space wrap className="case-workbench-card__actions">
        {reviewable ? <Link to={`/electronic-inspection/cases/${encodeURIComponent(shell.case_id)}`}><Button type="primary">打开案件</Button></Link> : <Button disabled>等待解析完成</Button>}
        {sourceRequiresReselection && <SourceStatusBadge status="requires_reselection" />}
        {!archiveSummary && canRetry && <Button onClick={onRetry} loading={actionBusy}>重试解析</Button>}
        {!archiveSummary && canCancel && <Button danger onClick={onCancel} loading={actionBusy}>取消任务</Button>}
        {!archiveSummary && reviewable && <Button onClick={onArchivePrecheck}>归档前检查</Button>}
        {exportReady && onExport && (
          <Button type="primary" onClick={onExport} loading={exporting || actionBusy}>统一导出</Button>
        )}
        {archiveAction && (
          <Button
            danger={archiveAction === 'cancel'}
            onClick={() => onArchiveAction?.(archiveAction)}
            loading={actionBusy}
          >{archiveSummary ? archiveActionLabel(archiveAction, archiveSummary) : ACTION_LABELS[archiveAction]}</Button>
        )}
        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
          <Button aria-label="更多操作" icon={<MoreOutlined />} disabled={actionBusy} />
        </Dropdown>
      </Space>
    </Card>
  )
}
