import {
  ARCHIVE_CARD_ERROR_SUMMARY_MAX_LENGTH,
  ARCHIVE_PROGRESS_KIND,
  ARCHIVE_STAGE_TRANSITIONS,
  ARCHIVE_TASK_ACTIONS_BY_STATUS,
  ARCHIVE_WORKER_STATE_TRANSITIONS,
  ARCHIVE_WORKFLOW_MILESTONES,
  ARCHIVE_WORKFLOW_STAGE_COUNT,
  TASK_STATUS_TRANSITIONS,
} from '../constants'
import type {
  ArchiveTaskAction,
  ArchiveTaskCardSummary,
  ArchiveWorkerState,
  ArchiveWorkflowStage,
  TaskRecord,
  TaskStage,
  TaskStatus,
} from '../types'

const WORKFLOW_STAGES = new Set<ArchiveWorkflowStage>(
  ARCHIVE_WORKFLOW_MILESTONES.map(milestone => milestone.stage),
)

export function isLegalArchiveStageTransition(
  from: ArchiveWorkflowStage,
  to: ArchiveWorkflowStage,
): boolean {
  return ARCHIVE_STAGE_TRANSITIONS[from].includes(to)
}

export function isLegalArchiveWorkerStateTransition(
  from: ArchiveWorkerState,
  to: ArchiveWorkerState,
): boolean {
  return ARCHIVE_WORKER_STATE_TRANSITIONS[from].includes(to)
}

export function isLegalArchiveTaskStatusTransition(from: TaskStatus, to: TaskStatus): boolean {
  return TASK_STATUS_TRANSITIONS[from].includes(to)
}

export function getArchiveAllowedActions(status: TaskStatus): ArchiveTaskAction[] {
  return [...ARCHIVE_TASK_ACTIONS_BY_STATUS[status]]
}

export function sanitizeArchiveErrorSummary(value: string | null | undefined): string | null {
  if (!value?.trim()) return null
  const withoutTechnicalLines = value
    .split(/\r?\n/)
    .filter(line => !/^\s*(?:at\s|traceback|file\s+".*",\s+line\s+\d+)/i.test(line))
    .join(' ')
  const redacted = withoutTechnicalLines
    .replace(/\b[A-Za-z]:[\\/][^\s,;)]*/g, '[本机路径已隐藏]')
    .replace(/\\\\[^\\\s]+\\[^\s,;)]*/g, '[本机路径已隐藏]')
    .replace(/\/(?:Users|home|tmp|var|etc|opt)\/[^\s,;)]*/gi, '[本机路径已隐藏]')
    .replace(/\s+/g, ' ')
    .trim()
  if (!redacted) return null
  return redacted.length <= ARCHIVE_CARD_ERROR_SUMMARY_MAX_LENGTH
    ? redacted
    : `${redacted.slice(0, ARCHIVE_CARD_ERROR_SUMMARY_MAX_LENGTH - 1)}…`
}

export function toArchiveTaskCardSummary(task: TaskRecord): ArchiveTaskCardSummary {
  if (task.kind !== 'archive') throw new Error('INVALID_ARCHIVE_CARD_PROJECTION')
  const stage = resolveWorkflowStage(task)
  const milestoneIndex = ARCHIVE_WORKFLOW_MILESTONES.findIndex(item => item.stage === stage)
  const milestone = ARCHIVE_WORKFLOW_MILESTONES[milestoneIndex]
  validateCurrentMilestone(task, stage, milestone.percent, milestoneIndex + 1)

  return {
    task_id: task.task_id,
    case_id: task.case_id,
    status: task.status,
    progress_kind: ARCHIVE_PROGRESS_KIND,
    stage,
    stage_label: milestone.label,
    stage_index: milestoneIndex + 1,
    stage_count: ARCHIVE_WORKFLOW_STAGE_COUNT,
    percent: milestone.percent,
    started_at: task.started_at ?? null,
    updated_at: task.updated_at ?? task.finished_at ?? task.started_at ?? task.created_at,
    finished_at: task.finished_at ?? null,
    last_heartbeat_at: task.last_heartbeat_at ?? null,
    output_bytes: normalizeActivityMetric(task.output_bytes),
    output_volume_count: normalizeActivityMetric(task.output_volume_count),
    last_output_change_at: task.last_output_change_at ?? null,
    worker_state: task.worker_state ?? getLegacyWorkerState(task.status),
    error_summary: shouldShowError(task.status)
      ? sanitizeArchiveErrorSummary(task.error_summary)
      : null,
    allowed_actions: getArchiveAllowedActions(task.status),
  }
}

function resolveWorkflowStage(task: TaskRecord): ArchiveWorkflowStage {
  if (task.status === 'succeeded') return 'completed'
  if (WORKFLOW_STAGES.has(task.stage as ArchiveWorkflowStage)) {
    return task.stage as ArchiveWorkflowStage
  }
  if (task.progress_kind === ARCHIVE_PROGRESS_KIND) {
    throw new Error('INVALID_TASK_PROGRESS')
  }
  return legacyStageFallback(task.stage)
}

function legacyStageFallback(stage: TaskStage): ArchiveWorkflowStage {
  if (stage === 'planning') return 'inventory'
  return 'queued'
}

function validateCurrentMilestone(
  task: TaskRecord,
  stage: ArchiveWorkflowStage,
  percent: number,
  stageIndex: number,
): void {
  if (task.progress_kind !== ARCHIVE_PROGRESS_KIND) return
  if (
    task.stage !== stage
    || task.percent !== percent
    || (task.stage_index !== undefined && task.stage_index !== stageIndex)
    || (task.stage_count !== undefined && task.stage_count !== ARCHIVE_WORKFLOW_STAGE_COUNT)
  ) {
    throw new Error('INVALID_TASK_PROGRESS')
  }
}

function normalizeActivityMetric(value: number | null | undefined): number | null {
  return Number.isSafeInteger(value) && Number(value) >= 0 ? Number(value) : null
}

function getLegacyWorkerState(status: TaskStatus): ArchiveWorkerState {
  if (status === 'interrupted') return 'waiting_reclaim'
  if (['succeeded', 'failed_retryable', 'failed_terminal', 'cancelled'].includes(status)) {
    return 'released'
  }
  return 'unassigned'
}

function shouldShowError(status: TaskStatus): boolean {
  return ['interrupted', 'failed_retryable', 'failed_terminal', 'cancelled', 'blocked'].includes(status)
}
