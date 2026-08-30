import { describe, expect, it } from 'vitest'
import {
  ARCHIVE_PROGRESS_KIND,
  ARCHIVE_WORKFLOW_MILESTONE_PERCENTS,
  ARCHIVE_WORKFLOW_MILESTONES,
} from '@biji/shared/constants'
import type { TaskRecord, TaskStatus } from '@biji/shared/types'
import {
  getArchiveAllowedActions,
  isLegalArchiveStageTransition,
  isLegalArchiveTaskStatusTransition,
  isLegalArchiveWorkerStateTransition,
  toArchiveTaskCardSummary,
} from '@biji/shared/utils'

function archiveTask(overrides: Partial<TaskRecord> = {}): TaskRecord {
  return {
    schema_version: 1,
    task_id: 'task-SYNTHETIC-001',
    case_id: 'case-SYNTHETIC-001',
    kind: 'archive',
    status: 'running',
    stage: 'winrar',
    percent: 30,
    counters: {},
    input_revision: 7,
    attempt: 1,
    cancel_requested: false,
    created_at: '2026-07-30T01:00:00.000Z',
    started_at: '2026-07-30T01:01:00.000Z',
    updated_at: '2026-07-30T01:02:00.000Z',
    progress_kind: ARCHIVE_PROGRESS_KIND,
    stage_label: '正在创建 RAR 分卷',
    stage_index: 4,
    stage_count: 9,
    last_heartbeat_at: '2026-07-30T01:02:00.000Z',
    output_bytes: 11_200_000_000,
    output_volume_count: 3,
    last_output_change_at: '2026-07-30T01:01:55.000Z',
    worker_state: 'owned_running',
    allowed_actions: ['cancel'],
    revision: 3,
    ...overrides,
  }
}

describe('Phase 3 archive workflow milestone contract', () => {
  it('fixes the versioned milestone sequence and safe labels', () => {
    expect(ARCHIVE_WORKFLOW_MILESTONE_PERCENTS).toEqual([0, 10, 20, 30, 75, 85, 90, 95, 100])
    expect(ARCHIVE_WORKFLOW_MILESTONES.map(item => item.stage)).toEqual([
      'queued', 'inventory', 'preflight_verified', 'winrar', 'integrity',
      'integrity_verified', 'hash', 'manifest', 'completed',
    ])
    expect(ARCHIVE_WORKFLOW_MILESTONES[3]).toEqual({
      stage: 'winrar', percent: 30, label: '正在创建 RAR 分卷',
    })
  })

  it('allows only the same or next real workflow stage', () => {
    expect(isLegalArchiveStageTransition('queued', 'inventory')).toBe(true)
    expect(isLegalArchiveStageTransition('winrar', 'winrar')).toBe(true)
    expect(isLegalArchiveStageTransition('winrar', 'integrity')).toBe(true)
    expect(isLegalArchiveStageTransition('winrar', 'hash')).toBe(false)
    expect(isLegalArchiveStageTransition('integrity', 'winrar')).toBe(false)
  })

  it('fixes task and Worker ownership transitions', () => {
    expect(isLegalArchiveTaskStatusTransition('queued', 'running')).toBe(true)
    expect(isLegalArchiveTaskStatusTransition('running', 'succeeded')).toBe(true)
    expect(isLegalArchiveTaskStatusTransition('succeeded', 'running')).toBe(false)
    expect(isLegalArchiveWorkerStateTransition('unassigned', 'starting')).toBe(true)
    expect(isLegalArchiveWorkerStateTransition('starting', 'owned_running')).toBe(true)
    expect(isLegalArchiveWorkerStateTransition('owned_running', 'waiting_reclaim')).toBe(true)
    expect(isLegalArchiveWorkerStateTransition('released', 'owned_running')).toBe(false)
  })

  it.each<[TaskStatus, string[]]>([
    ['queued', ['cancel']],
    ['running', ['cancel']],
    ['cancelling', []],
    ['interrupted', ['view_details', 'retry']],
    ['succeeded', ['view_result']],
    ['failed_retryable', ['view_details', 'retry']],
    ['failed_terminal', ['view_details']],
    ['cancelled', ['view_details', 'retry']],
    ['blocked', ['view_details', 'cancel']],
  ])('derives allowed actions for %s', (status, actions) => {
    expect(getArchiveAllowedActions(status)).toEqual(actions)
  })

  it('keeps WinRAR at 30 while exposing activity without deriving a ratio', () => {
    const summary = toArchiveTaskCardSummary(archiveTask())
    expect(summary).toMatchObject({
      stage: 'winrar',
      stage_index: 4,
      stage_count: 9,
      percent: 30,
      progress_kind: 'workflow_milestone',
      output_volume_count: 3,
      output_bytes: 11_200_000_000,
      worker_state: 'owned_running',
      allowed_actions: ['cancel'],
    })
    expect(summary).not.toHaveProperty('compression_percent')
  })

  it('preserves the last confirmed milestone for failure, cancellation and recovery states', () => {
    const failed = toArchiveTaskCardSummary(archiveTask({
      status: 'failed_retryable', worker_state: 'released', error_summary: 'SYNTHETIC 磁盘空间不足',
    }))
    const cancelled = toArchiveTaskCardSummary(archiveTask({
      status: 'cancelled', worker_state: 'released', finished_at: '2026-07-30T01:03:00.000Z',
    }))
    const recovering = toArchiveTaskCardSummary(archiveTask({
      status: 'interrupted', worker_state: 'recovering',
    }))
    const waiting = toArchiveTaskCardSummary(archiveTask({
      status: 'interrupted', worker_state: 'waiting_reclaim',
    }))
    expect(failed).toMatchObject({ percent: 30, allowed_actions: ['view_details', 'retry'] })
    expect(cancelled).toMatchObject({ percent: 30, allowed_actions: ['view_details', 'retry'] })
    expect(recovering.worker_state).toBe('recovering')
    expect(waiting.worker_state).toBe('waiting_reclaim')
  })

  it('reports success only at the completed milestone', () => {
    expect(toArchiveTaskCardSummary(archiveTask({
      status: 'succeeded',
      stage: 'completed',
      percent: 100,
      stage_index: 9,
      worker_state: 'released',
      finished_at: '2026-07-30T01:20:00.000Z',
    }))).toMatchObject({
      stage: 'completed', percent: 100, allowed_actions: ['view_result'],
    })
  })

  it('rejects a fabricated continuous percent or skipped milestone metadata', () => {
    expect(() => toArchiveTaskCardSummary(archiveTask({ percent: 31 }))).toThrow('INVALID_TASK_PROGRESS')
    expect(() => toArchiveTaskCardSummary(archiveTask({ stage_index: 5 }))).toThrow('INVALID_TASK_PROGRESS')
  })
})

describe('ArchiveTaskCardSummary safety projection', () => {
  it('omits internal Worker, lease, path, stack and log fields', () => {
    const internal = {
      ...archiveTask({ status: 'failed_retryable', error_summary: 'SYNTHETIC failure' }),
      worker_id: 'worker-SYNTHETIC-secret',
      lease_id: 'lease-SYNTHETIC-secret',
      absolute_path: 'C:\\Users\\TEST\\secret.rar',
      stack: 'SYNTHETIC STACK',
      technical_log: ['SYNTHETIC raw log'],
      internal_diagnostics: { commandline: 'WinRAR.exe secret' },
    } as unknown as TaskRecord
    const serialized = JSON.stringify(toArchiveTaskCardSummary(internal))
    for (const forbidden of ['worker_id', 'lease_id', 'absolute_path', 'stack', 'technical_log', 'internal_diagnostics']) {
      expect(serialized).not.toContain(forbidden)
    }
  })

  it('redacts paths, removes stack lines and bounds a long safe error summary', () => {
    const summary = toArchiveTaskCardSummary(archiveTask({
      status: 'failed_retryable',
      worker_state: 'released',
      error_summary: `SYNTHETIC 输出失败 C:\\Users\\TEST\\secret\\part01.rar\n  at worker (archive.ts:10)\n${'原因'.repeat(120)}`,
    }))
    expect(summary.error_summary?.length).toBeLessThanOrEqual(160)
    expect(summary.error_summary).toContain('[本机路径已隐藏]')
    expect(summary.error_summary).not.toContain('C:\\Users')
    expect(summary.error_summary).not.toContain('at worker')
  })

  it('accepts missing optional activity fields and projects legacy task records safely', () => {
    const legacy = archiveTask({
      stage: 'planning',
      percent: 37,
      progress_kind: undefined,
      stage_label: undefined,
      stage_index: undefined,
      stage_count: undefined,
      updated_at: undefined,
      last_heartbeat_at: undefined,
      output_bytes: undefined,
      output_volume_count: undefined,
      last_output_change_at: undefined,
      worker_state: undefined,
      allowed_actions: undefined,
    })
    const summary = toArchiveTaskCardSummary(legacy)
    expect(summary).toMatchObject({
      stage: 'inventory',
      percent: 10,
      progress_kind: 'workflow_milestone',
      output_bytes: null,
      output_volume_count: null,
      worker_state: 'unassigned',
      updated_at: legacy.started_at,
    })
  })
})
