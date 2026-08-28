// 第 11 层：FE_Components — 单个持久化案件工作台卡片。
import React from 'react'
import { Button, Card, Dropdown, Tag, Tooltip, Typography } from 'antd'
import type { MenuProps } from 'antd'
import { FolderOpenOutlined, FolderOutlined, MoreOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import type {
  ArchiveCompletionStatus, ArchiveTaskAction, ArchiveTaskCardSummary, CaseShell, TaskRecord,
} from '@biji/shared/types'
import { SourceStatusBadge } from './SourceStatusBadge'
import { ArchiveStatusPanel } from './ArchiveStatusPanel'

const { Text } = Typography

type CardPhase =
  | 'parsing'
  | 'parse_failed'
  | 'ready'
  | 'archiving'
  | 'archive_failed'
  | 'disc_pending'
  | 'archive_complete'
  | 'archive_result_pending'
  | 'exported'

interface Props {
  shell: CaseShell
  task?: TaskRecord
  sourceRequiresReselection?: boolean
  onRetry: () => void
  onCancel: () => void
  onDelete: () => void
  archiveSummary?: ArchiveTaskCardSummary
  onArchiveAction?: (action: ArchiveTaskAction) => void
  actionBusy?: boolean
  completionStatus?: ArchiveCompletionStatus
  onExport?: () => void
  exporting?: boolean
  canOpenExportDirectory?: boolean
  onOpenExportDirectory?: () => void
  openingExportDirectory?: boolean
}

const ACTION_LABELS: Record<ArchiveTaskAction, string> = {
  cancel: '取消归档',
  retry: '重试归档',
  view_result: '查看结果',
  view_details: '查看详情',
}

const ACTIVE_ARCHIVE_STATUSES = new Set(['queued', 'running', 'blocked', 'cancelling'])
const FAILED_ARCHIVE_STATUSES = new Set([
  'failed_retryable', 'failed_terminal', 'interrupted', 'cancelled',
])

function displayDate(value: string | null | undefined): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未知'
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function resolvePhase(
  shell: CaseShell,
  task?: TaskRecord,
  archiveSummary?: ArchiveTaskCardSummary,
  completionStatus?: ArchiveCompletionStatus,
): CardPhase {
  if (shell.lifecycle === 'exported') return 'exported'

  const parsingLifecycle = shell.lifecycle === 'case_created'
    || shell.lifecycle === 'parse_queued'
    || shell.lifecycle === 'parsing'

  if (shell.lifecycle === 'parse_failed_retryable'
    || (parsingLifecycle && (task?.status === 'failed_retryable' || task?.status === 'interrupted'))) {
    return 'parse_failed'
  }
  if (parsingLifecycle) return 'parsing'

  if (completionStatus === 'archive_complete') return 'archive_complete'
  if (completionStatus === 'disc_pending') return 'disc_pending'
  if (shell.lifecycle === 'archive_verified') return 'archive_result_pending'

  if (archiveSummary && ACTIVE_ARCHIVE_STATUSES.has(archiveSummary.status)) return 'archiving'
  if (archiveSummary && FAILED_ARCHIVE_STATUSES.has(archiveSummary.status)) return 'archive_failed'

  if (completionStatus === 'compressing'
    || shell.lifecycle === 'archive_queued'
    || shell.lifecycle === 'archiving'
    || shell.lifecycle === 'cancelling') return 'archiving'

  if (shell.lifecycle === 'archive_interrupted'
    || shell.lifecycle === 'cancelled') return 'archive_failed'

  return 'ready'
}

function phaseLabel(phase: CardPhase): string {
  switch (phase) {
    case 'parsing': return '解析中'
    case 'parse_failed': return '解析失败'
    case 'ready': return '待处理'
    case 'archiving':
    case 'archive_result_pending': return '处理中'
    case 'archive_failed': return '处理失败'
    case 'disc_pending': return '待补盘号'
    case 'archive_complete': return '待导出'
    case 'exported': return '已导出'
  }
}

function archiveActionLabel(action: ArchiveTaskAction, summary: ArchiveTaskCardSummary): string {
  if (action === 'view_details' && summary.status.includes('failed')) return '查看原因'
  if (action === 'retry' && summary.status === 'cancelled') return '重新归档'
  return ACTION_LABELS[action]
}

function recommendedArchiveAction(summary?: ArchiveTaskCardSummary): ArchiveTaskAction | undefined {
  if (!summary || !FAILED_ARCHIVE_STATUSES.has(summary.status)) return undefined
  return (['retry', 'view_details'] as const).find(action => summary.allowed_actions.includes(action))
}

function casePath(caseId: string): string {
  return `/electronic-inspection/cases/${encodeURIComponent(caseId)}`
}

export function CaseCard({
  shell, task, archiveSummary, sourceRequiresReselection, onRetry, onCancel,
  onDelete, onArchiveAction, actionBusy = false, completionStatus, onExport,
  exporting = false, canOpenExportDirectory = false, onOpenExportDirectory,
  openingExportDirectory = false,
}: Props) {
  const phase = resolvePhase(shell, task, archiveSummary, completionStatus)
  const reviewable = shell.report_available && shell.lifecycle !== 'parse_failed_retryable'
  const canCancelParse = task?.status === 'queued' || task?.status === 'running'
  const archiveMainAction = recommendedArchiveAction(archiveSummary)
  const finishedAt = archiveSummary?.finished_at ?? shell.updated_at

  const menuItems: MenuProps['items'] = []
  if (phase === 'exported') {
    if (reviewable) {
      menuItems.push({
        key: 'open_case',
        label: <Link to={casePath(shell.case_id)}>打开案件</Link>,
      })
    }
    if (onExport) {
      menuItems.push({ key: 'export_again', label: '再次导出', onClick: onExport })
    }
  } else {
    if (phase === 'archive_complete' && reviewable) {
      menuItems.push({
        key: 'open_case',
        label: <Link to={casePath(shell.case_id)}>打开案件</Link>,
      })
    }
    menuItems.push({ key: 'delete', label: '删除案件', danger: true, onClick: onDelete })
  }

  if (phase === 'parsing' && canCancelParse) {
    menuItems.push({ key: 'cancel_parse', label: '取消任务', danger: true, onClick: onCancel })
  }

  if (phase === 'archiving' || phase === 'archive_failed') {
    for (const action of archiveSummary?.allowed_actions ?? []) {
      if (action === 'view_result' || action === archiveMainAction) continue
      menuItems.push({
        key: `archive_${action}`,
        label: archiveActionLabel(action, archiveSummary!),
        danger: action === 'cancel',
        onClick: () => onArchiveAction?.(action),
      })
    }
  }

  const renderPhaseDetails = () => {
    switch (phase) {
      case 'exported':
        return (
          <div className="case-workbench-card__result">
            <strong>导出完成</strong>
            <Text type="secondary">完成于 {displayDate(shell.updated_at)}</Text>
            <span>文件已成功导出，可以删除当前案件</span>
          </div>
        )
      case 'archive_complete':
        return (
          <div className="case-workbench-card__result">
            <strong>压缩完成</strong>
            <Text type="secondary">
              {archiveSummary?.output_volume_count !== null && archiveSummary?.output_volume_count !== undefined
                ? `${archiveSummary.output_volume_count} 个分卷 · ` : ''}
              完成于 {displayDate(finishedAt)}
            </Text>
            <span>压缩已完成，可以统一导出</span>
          </div>
        )
      case 'disc_pending':
        return (
          <div className="case-workbench-card__result">
            <strong>压缩完成，等待补充盘号</strong>
            <span>打开案件补充盘号后即可统一导出</span>
          </div>
        )
      case 'archiving':
        return (
          <>
            {archiveSummary
              ? <ArchiveStatusPanel summary={archiveSummary} />
              : <div className="case-workbench-card__result"><strong>后台压缩中</strong></div>}
            <div className="case-workbench-card__guidance">压缩任务正在后台运行，可继续审核和编辑</div>
          </>
        )
      case 'archive_failed':
        return archiveSummary
          ? <ArchiveStatusPanel summary={archiveSummary} />
          : <div className="case-workbench-card__result"><strong>归档任务未完成</strong><span>可打开案件查看当前情况</span></div>
      case 'archive_result_pending':
        return <div className="case-workbench-card__result"><strong>正在确认归档结果……</strong><span>可继续审核和编辑</span></div>
      case 'parse_failed':
        return <div className="case-workbench-card__result"><strong>报告解析失败</strong><span>可以重新提交解析任务</span></div>
      case 'parsing':
        return <div className="case-workbench-card__result"><strong>正在解析报告……</strong></div>
      case 'ready':
        return (
          <div className="case-workbench-card__result">
            <strong>报告解析完成</strong>
            <span>可以进入案件开始审核和编辑</span>
            <Text type="secondary">更新于 {displayDate(shell.updated_at)}</Text>
          </div>
        )
    }
  }

  const renderRecommendedAction = () => {
    if (phase === 'parse_failed') {
      return <Button type="primary" onClick={onRetry} loading={actionBusy}>重试解析</Button>
    }
    if (phase === 'archive_complete' && onExport) {
      return <Button type="primary" onClick={onExport} loading={exporting || actionBusy}>统一导出</Button>
    }
    if (phase === 'exported') {
      if (exporting) {
        return <Button type="primary" loading>再次导出</Button>
      }
      return <Button type="primary" danger onClick={onDelete} disabled={actionBusy}>删除案件</Button>
    }
    if (phase === 'archive_failed' && archiveMainAction && archiveSummary) {
      return (
        <Button type="primary" onClick={() => onArchiveAction?.(archiveMainAction)} loading={actionBusy}>
          {archiveActionLabel(archiveMainAction, archiveSummary)}
        </Button>
      )
    }
    if ((phase === 'ready' || phase === 'archiving' || phase === 'disc_pending'
      || phase === 'archive_result_pending' || phase === 'archive_failed') && reviewable) {
      return <Link to={casePath(shell.case_id)}><Button type="primary">打开案件</Button></Link>
    }
    return null
  }

  return (
    <Card
      className="case-workbench-card"
      title={(
        <span className="case-workbench-card__title" title={shell.case_name}>
          <span className="case-workbench-card__title-icon" aria-hidden="true">
            <FolderOutlined />
          </span>
          <span className="case-workbench-card__title-text">{shell.case_name || '案件名称待解析'}</span>
        </span>
      )}
      extra={<Tag color={phase === 'exported' ? 'success' : undefined} className="case-workbench-card__status">{phaseLabel(phase)}</Tag>}
    >
      <div className="case-workbench-card__number" title={shell.case_number || '案件编号待解析'}>
        {shell.case_number || '案件编号待解析'}
      </div>
      {sourceRequiresReselection && <SourceStatusBadge status="requires_reselection" />}
      {renderPhaseDetails()}
      <div className="case-workbench-card__actions">
        <div>{renderRecommendedAction()}</div>
        <div className="case-workbench-card__utilities">
          {canOpenExportDirectory && onOpenExportDirectory && (
            <Tooltip title="打开导出文件夹">
              <Button
                aria-label="打开导出文件夹"
                icon={<FolderOpenOutlined />}
                onClick={onOpenExportDirectory}
                loading={openingExportDirectory}
                disabled={actionBusy || exporting}
              />
            </Tooltip>
          )}
          <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <Button aria-label="更多操作" icon={<MoreOutlined />} disabled={actionBusy || exporting} />
          </Dropdown>
        </div>
      </div>
    </Card>
  )
}
