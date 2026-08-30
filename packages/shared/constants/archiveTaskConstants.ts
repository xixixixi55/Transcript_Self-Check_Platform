import type {
  ArchiveTaskAction,
  ArchiveWorkerState,
  ArchiveWorkflowMilestonePercent,
  ArchiveWorkflowStage,
  TaskStatus,
} from '../types'

export const ARCHIVE_PROGRESS_KIND = 'workflow_milestone' as const

export const ARCHIVE_WORKFLOW_MILESTONES = [
  { stage: 'queued', percent: 0, label: '等待归档或资源准入' },
  { stage: 'inventory', percent: 10, label: '正在核对文件清单与路径' },
  { stage: 'preflight_verified', percent: 20, label: '归档前置检查通过' },
  { stage: 'winrar', percent: 30, label: '正在创建 RAR 分卷' },
  { stage: 'integrity', percent: 75, label: 'RAR 分卷创建完成，正在校验' },
  { stage: 'integrity_verified', percent: 85, label: '分卷完整性校验通过' },
  { stage: 'hash', percent: 90, label: '正在计算文件哈希' },
  { stage: 'manifest', percent: 95, label: '正在写入并验证 Manifest' },
  { stage: 'completed', percent: 100, label: '归档完成' },
] as const satisfies readonly {
  stage: ArchiveWorkflowStage
  percent: ArchiveWorkflowMilestonePercent
  label: string
}[]

export const ARCHIVE_WORKFLOW_STAGE_COUNT = ARCHIVE_WORKFLOW_MILESTONES.length
export const ARCHIVE_WORKFLOW_MILESTONE_PERCENTS = ARCHIVE_WORKFLOW_MILESTONES.map(
  milestone => milestone.percent,
) as readonly ArchiveWorkflowMilestonePercent[]

export const ARCHIVE_STAGE_TRANSITIONS: Readonly<
  Record<ArchiveWorkflowStage, readonly ArchiveWorkflowStage[]>
> = {
  queued: ['queued', 'inventory'],
  inventory: ['inventory', 'preflight_verified'],
  preflight_verified: ['preflight_verified', 'winrar'],
  winrar: ['winrar', 'integrity'],
  integrity: ['integrity', 'integrity_verified'],
  integrity_verified: ['integrity_verified', 'hash'],
  hash: ['hash', 'manifest'],
  manifest: ['manifest', 'completed'],
  completed: ['completed'],
}

export const ARCHIVE_WORKER_STATE_TRANSITIONS: Readonly<
  Record<ArchiveWorkerState, readonly ArchiveWorkerState[]>
> = {
  unassigned: ['unassigned', 'starting', 'recovering', 'waiting_reclaim'],
  starting: ['starting', 'owned_running', 'waiting_reclaim', 'released'],
  owned_running: ['owned_running', 'recovering', 'waiting_reclaim', 'released'],
  recovering: ['recovering', 'starting', 'owned_running', 'waiting_reclaim', 'released'],
  waiting_reclaim: ['waiting_reclaim', 'starting', 'recovering', 'owned_running', 'released'],
  released: ['released'],
}

export const ARCHIVE_TASK_ACTIONS_BY_STATUS: Readonly<
  Record<TaskStatus, readonly ArchiveTaskAction[]>
> = {
  queued: ['cancel'],
  running: ['cancel'],
  cancelling: [],
  interrupted: ['view_details', 'retry'],
  succeeded: ['view_result'],
  failed_retryable: ['view_details', 'retry'],
  failed_terminal: ['view_details'],
  cancelled: ['view_details', 'retry'],
  blocked: ['view_details', 'cancel'],
}

export const ARCHIVE_CARD_ERROR_SUMMARY_MAX_LENGTH = 160
