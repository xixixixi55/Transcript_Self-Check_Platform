// Layer 11: FE_Components — safe case/task lifecycle labels.
import React from 'react'
import { Tag } from 'antd'
import type { CaseLifecycle, TaskRecord } from '@biji/shared/types'

const LIFECYCLE_LABELS: Record<CaseLifecycle, string> = {
  case_created: '已创建', parse_queued: '等待解析', parsing: '解析中', review_ready: '待审核',
  parse_failed_retryable: '解析失败，可重试', archive_deferred: '暂不归档', archive_interrupted: '归档已中断', archive_queued: '等待归档',
  archiving: '归档中', archive_verified: '归档完成', exporting_word: '导出中', exported: '已导出',
  record_retention_expired: '记录待清理', record_cleaned: '记录已清理', cancelling: '取消中', cancelled: '已取消',
}
const TASK_COLORS: Record<string, string> = {
  queued: 'blue', running: 'processing', succeeded: 'green', failed_retryable: 'error',
  failed_terminal: 'error', interrupted: 'warning', cancelling: 'warning', cancelled: 'default', blocked: 'warning',
}

export function CaseStatusBadge({ lifecycle, task }: { lifecycle: CaseLifecycle; task?: TaskRecord }) {
  const label = task?.status === 'failed_retryable' ? '解析失败，可重试'
    : task?.status === 'interrupted' ? '任务已中断，可重试' : LIFECYCLE_LABELS[lifecycle]
  return <Tag color={task ? TASK_COLORS[task.status] : undefined}>{label}</Tag>
}
