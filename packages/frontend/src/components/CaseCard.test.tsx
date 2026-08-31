import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import type { ArchiveTaskCardSummary, CaseShell } from '@biji/shared/types'
import { CaseCard } from './CaseCard'

const NOW = new Date('2026-07-30T12:00:00Z')
const shell: CaseShell & { entrust_unit: string; entrust_persons: string[] } = {
  schema_version: 1,
  case_id: 'case-SYNTHETIC-T012',
  case_number: 'SYNTHETIC-TEST-VERY-LONG-CASE-NUMBER-000000000000000000000012',
  case_name: 'SYNTHETIC/TEST very long case name that must not expand the card width',
  case_summary: 'SYNTHETIC/TEST summary',
  entrust_unit: 'SYNTHETIC/TEST 委托单位',
  entrust_persons: ['SYNTHETIC/TEST 委托人甲', 'SYNTHETIC/TEST 委托人乙'],
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
    expect(screen.queryByLabelText(/案件序号/)).toBeNull()
    expect(screen.getByText('待处理')).toBeTruthy()
    expect(screen.queryByText('报告解析完成')).toBeNull()
    expect(screen.queryByText('可以进入案件开始审核和编辑')).toBeNull()
    expect(screen.getByText(/更新于 2026-07-30/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '打开案件' })).toBeTruthy()
    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(screen.queryByText(/总体里程碑/)).toBeNull()
  })

  it('keeps the case name as title and replaces the case number with entrust information', () => {
    renderCard()
    expect(screen.getAllByText(shell.case_name)).toHaveLength(1)
    expect(screen.getByText('委托人：')).toBeTruthy()
    expect(screen.getByText('SYNTHETIC/TEST 委托人甲、SYNTHETIC/TEST 委托人乙')).toBeTruthy()
    expect(screen.getByText('委托单位：')).toBeTruthy()
    expect(screen.getByText(shell.entrust_unit)).toBeTruthy()
    expect(screen.queryByText(shell.case_number!)).toBeNull()
    expect(screen.queryByText('案件名称')).toBeNull()
    expect(screen.queryByText(shell.case_summary)).toBeNull()
    expect(screen.getByText(/更新于 2026-07-30/)).toBeTruthy()
  })

  it('shows per-field fallbacks while entrust information is unavailable', () => {
    render(
      <MemoryRouter>
        <CaseCard
          shell={{ ...shell, entrust_unit: '', entrust_persons: [] }}
          onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('委托人待解析')).toBeTruthy()
    expect(screen.getByText('委托单位待解析')).toBeTruthy()
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
    expect(screen.getByText('已生成 3 个分卷（仍在压缩） · 已写出约 11.2 GB · 最后活动：刚刚')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/\b(?:31|50|74)%/)
    expect(document.querySelectorAll('.archive-status-panel__activity-line')).toHaveLength(2)
  })

  it.each([
    ['inventory', '正在核对文件清单与路径', 10, 2],
    ['integrity', 'RAR 分卷创建完成，正在校验', 75, 5],
    ['hash', '正在计算文件哈希', 90, 7],
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
        })} onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()}
          completionStatus="archive_complete" onExport={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('待导出')).toBeTruthy()
    expect(screen.getByText('压缩完成')).toBeTruthy()
    expect(screen.queryByText('总体里程碑 100% · 3 个分卷')).toBeNull()
    expect(screen.queryByText(/阶段 9/)).toBeNull()
    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(screen.getByRole('button', { name: '统一导出' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '查看结果' })).toBeNull()
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
