import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import type { ArchiveTaskCardSummary, CaseShell } from '@biji/shared/types'
import { CaseCard } from './CaseCard'

const NOW = new Date('2026-07-30T12:00:00Z')
const shell: CaseShell = {
  schema_version: 1,
  case_id: 'case-SYNTHETIC-T012',
  case_number: 'SYNTHETIC-TEST-VERY-LONG-CASE-NUMBER-000000000000000000000012',
  case_name: 'SYNTHETIC/TEST very long case name that must not expand the card width',
  case_summary: 'SYNTHETIC/TEST summary',
  source_id: 'source-SYNTHETIC-T012',
  parse_task_id: 'parse-SYNTHETIC-T012',
  lifecycle: 'review_ready',
  report_available: true,
  revision: 1,
  created_at: '2026-07-30T08:00:00Z',
  updated_at: '2026-07-30T11:00:00Z',
}

function summary(overrides: Partial<ArchiveTaskCardSummary> = {}): ArchiveTaskCardSummary {
  return {
    task_id: 'archive-SYNTHETIC-T012',
    case_id: shell.case_id,
    status: 'running',
    progress_kind: 'workflow_milestone',
    stage: 'winrar',
    stage_label: '正在创建 RAR 分卷',
    stage_index: 4,
    stage_count: 9,
    percent: 30,
    started_at: '2026-07-30T11:42:00Z',
    updated_at: '2026-07-30T12:00:00Z',
    finished_at: null,
    last_heartbeat_at: '2026-07-30T12:00:00Z',
    output_bytes: Math.round(11.2 * 1024 ** 3),
    output_volume_count: 3,
    last_output_change_at: '2026-07-30T12:00:00Z',
    worker_state: 'owned_running',
    error_summary: null,
    allowed_actions: ['cancel'],
    ...overrides,
  }
}

function renderCard(archiveSummary?: ArchiveTaskCardSummary) {
  const onArchiveAction = vi.fn()
  render(
    <MemoryRouter>
      <CaseCard
        shell={shell}
        archiveSummary={archiveSummary}
        onRetry={vi.fn()}
        onCancel={vi.fn()}
        onDelete={vi.fn()}
        onArchiveAction={onArchiveAction}
      />
    </MemoryRouter>,
  )
  return onArchiveAction
}

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: query.includes('prefers-reduced-motion'),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  })
})

describe('CaseCard archive task summary — Phase 3 card scenarios', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })

  it('shows an unarchived card without empty progress or activity metrics', () => {
    renderCard()
    expect(screen.getByText('未归档')).toBeTruthy()
    expect(screen.getByRole('button', { name: '归档前检查' })).toBeTruthy()
    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(screen.queryByText(/总体里程碑/)).toBeNull()
  })

  it('renders the persisted case name and summary on the card', () => {
    renderCard()
    expect(screen.getByText(shell.case_name)).toBeTruthy()
    expect(screen.getByText(shell.case_summary)).toBeTruthy()
  })

  it('shows queued and recovery states without claiming the task is running', () => {
    const { rerender } = render(
      <MemoryRouter>
        <CaseCard shell={shell} archiveSummary={summary({
          status: 'queued', stage: 'queued', stage_label: '等待归档或资源准入',
          stage_index: 1, percent: 0, worker_state: 'unassigned',
        })} onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('等待归档')).toBeTruthy()
    expect(screen.getByText('任务当前未在运行')).toBeTruthy()

    rerender(
      <MemoryRouter>
        <CaseCard shell={shell} archiveSummary={summary({
          status: 'interrupted', worker_state: 'waiting_reclaim',
          allowed_actions: ['view_details', 'retry'],
        })} onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('等待接管')).toBeTruthy()
    expect(screen.queryByRole('progressbar')).toBeNull()

    rerender(
      <MemoryRouter>
        <CaseCard shell={shell} archiveSummary={summary({
          status: 'interrupted', worker_state: 'recovering',
          allowed_actions: ['view_details', 'retry'],
        })} onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('恢复中')).toBeTruthy()
  })

  it('keeps long-running WinRAR at 30% and shows observable activity in two lines', () => {
    renderCard(summary())
    expect(screen.getByText('正在创建 RAR 分卷')).toBeTruthy()
    expect(screen.getByRole('progressbar', { name: '任务正在运行：正在创建 RAR 分卷' })).toBeTruthy()
    expect(screen.getByText('总体里程碑 30% · 已运行 18 分钟')).toBeTruthy()
    expect(screen.getByText('已检测 3 个分卷 · 已写出约 11.2 GB · 最后活动：刚刚')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/\b(?:31|50|74)%/)
    expect(document.querySelectorAll('.archive-status-panel__activity-line')).toHaveLength(2)
  })

  it.each([
    ['inventory', '正在核对文件清单与路径', 10, 2],
    ['integrity', 'RAR 分卷创建完成，正在校验', 75, 5],
    ['md5', '正在计算 MD5', 90, 7],
    ['manifest', '正在写入并验证 Manifest', 95, 8],
  ] as const)('shows confirmed workflow stage %s without inferred internal progress', (stage, label, percent, stageIndex) => {
    renderCard(summary({ stage, stage_label: label, percent, stage_index: stageIndex }))
    expect(screen.getByText(label)).toBeTruthy()
    expect(screen.getByText(new RegExp(`总体里程碑 ${percent}%`))).toBeTruthy()
    expect(screen.queryByRole('progressbar')).toBeNull()
  })

  it('replaces activity with safe failure, cancellation, and completion summaries', () => {
    const { rerender } = render(
      <MemoryRouter>
        <CaseCard shell={shell} archiveSummary={summary({
          status: 'failed_retryable',
          error_summary: 'SYNTHETIC 安全失败摘要，已截断且不包含技术细节。',
          allowed_actions: ['view_details', 'retry'],
        })} onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('归档失败')).toBeTruthy()
    expect(screen.getByText(/失败阶段：正在创建 RAR 分卷/)).toBeTruthy()
    expect(screen.getByText(/SYNTHETIC 安全失败摘要/)).toBeTruthy()

    rerender(
      <MemoryRouter>
        <CaseCard shell={shell} archiveSummary={summary({
          status: 'cancelled', finished_at: '2026-07-30T11:59:00Z',
          worker_state: 'released', allowed_actions: ['view_details', 'retry'],
        })} onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('已取消')).toBeTruthy()
    expect(screen.getByText(/取消时阶段/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '重新归档' })).toBeTruthy()

    rerender(
      <MemoryRouter>
        <CaseCard shell={shell} archiveSummary={summary({
          status: 'succeeded', stage: 'completed', stage_label: '归档完成',
          stage_index: 9, percent: 100, finished_at: '2026-07-30T11:59:00Z',
          worker_state: 'released', allowed_actions: ['view_result'],
        })} onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getAllByText('归档完成').length).toBeGreaterThan(0)
    expect(screen.getByText('总体里程碑 100% · 3 个分卷')).toBeTruthy()
    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(screen.getByRole('button', { name: '查看结果' })).toBeTruthy()
  })

  it('renders only actions explicitly present in allowed_actions', () => {
    const onArchiveAction = renderCard(summary({
      status: 'failed_terminal',
      error_summary: 'SYNTHETIC terminal failure',
      allowed_actions: ['view_details'],
    }))
    expect(screen.getByRole('button', { name: '查看原因' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '重试归档' })).toBeNull()
    expect(screen.queryByRole('button', { name: '取消归档' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看原因' }))
    expect(onArchiveAction).toHaveBeenCalledWith('view_details')
  })

  it('handles missing optional metrics, long text, narrow-card classes, and safe DTO isolation', () => {
    const unsafe = {
      ...summary({
        output_bytes: null,
        output_volume_count: null,
        last_output_change_at: null,
        last_heartbeat_at: null,
        error_summary: null,
      }),
      worker_id: 'WORKER-SECRET',
      lease_owner: 'LEASE-SECRET',
      local_path: 'C:\\REAL\\SECRET',
      stack: 'STACK-SECRET',
      logs: 'LOG-SECRET',
    } as ArchiveTaskCardSummary
    renderCard(unsafe)
    expect(document.querySelector('.case-workbench-card__title')).toBeTruthy()
    expect(document.querySelector('.archive-status-panel__activity-line--secondary')).toBeNull()
    expect(document.body.textContent).not.toMatch(/WORKER-SECRET|LEASE-SECRET|REAL\\SECRET|STACK-SECRET|LOG-SECRET/)
    expect(screen.getByText('正在创建 RAR 分卷')).toBeTruthy()
  })

  it('does not infer failure when heartbeat or output activity is old', () => {
    renderCard(summary({
      last_heartbeat_at: '2026-07-30T09:00:00Z',
      last_output_change_at: '2026-07-30T09:00:00Z',
    }))
    expect(screen.getByText('归档中')).toBeTruthy()
    expect(screen.getByText(/最后活动：3 小时前/)).toBeTruthy()
    expect(screen.queryByText('归档失败')).toBeNull()
  })

})
