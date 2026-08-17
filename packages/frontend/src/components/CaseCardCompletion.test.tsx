import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'
import type { ArchiveTaskCardSummary, CaseShell } from '@biji/shared/types'
import { CaseCard } from './CaseCard'

const shell: CaseShell = {
  schema_version: 1,
  case_id: 'case-SYNTHETIC-COMPLETION',
  case_name: 'SYNTHETIC/TEST completion card',
  case_summary: 'SYNTHETIC/TEST',
  source_id: 'source-SYNTHETIC-COMPLETION',
  parse_task_id: 'parse-SYNTHETIC-COMPLETION',
  lifecycle: 'archive_verified',
  report_available: true,
  revision: 1,
  created_at: '2026-07-30T08:00:00Z',
  updated_at: '2026-07-30T11:00:00Z',
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}</output>
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

describe('CaseCard archive completion states', () => {
  const activeSummary: ArchiveTaskCardSummary = {
    task_id: 'archive-SYNTHETIC-COMPLETION', case_id: shell.case_id,
    status: 'running', progress_kind: 'workflow_milestone', stage: 'manifest',
    stage_label: '正在写入并验证 Manifest', stage_index: 8, stage_count: 9, percent: 95,
    started_at: '2026-07-30T10:00:00Z', updated_at: '2026-07-30T11:00:00Z',
    finished_at: null, last_heartbeat_at: '2026-07-30T11:00:00Z', output_bytes: 1024,
    output_volume_count: 1, last_output_change_at: '2026-07-30T11:00:00Z',
    worker_state: 'owned_running', error_summary: null, allowed_actions: ['cancel'],
  }

  it('gives exported lifecycle precedence over stale active task details', () => {
    const onDelete = vi.fn()
    const onExport = vi.fn()
    render(
      <MemoryRouter>
        <CaseCard
          shell={{ ...shell, lifecycle: 'exported' }}
          archiveSummary={activeSummary}
          completionStatus="exported"
          onRetry={vi.fn()}
          onCancel={vi.fn()}
          onDelete={onDelete}
          onExport={onExport}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('已导出').className).toContain('ant-tag-success')
    expect(screen.getByText('导出完成')).toBeTruthy()
    expect(screen.getByText('文件已成功导出，可以删除当前案件')).toBeTruthy()
    expect(screen.queryByText(/阶段 8/)).toBeNull()
    expect(screen.queryByText('正在写入并验证 Manifest')).toBeNull()
    expect(screen.queryByText('归档中')).toBeNull()
    expect(screen.queryByRole('button', { name: '统一导出' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '删除案件' }))
    expect(onDelete).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByLabelText('更多操作'))
    expect(screen.getAllByRole('menuitem').map(item => item.textContent)).toEqual(['打开案件', '再次导出'])
    expect(screen.getByRole('menuitem', { name: '打开案件' })).toBeTruthy()
    fireEvent.click(screen.getByRole('menuitem', { name: '再次导出' }))
    expect(onExport).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('彻底删除')).toBeNull()
  })

  it('maps each phase to its actual visible recommended CTA', () => {
    const recommendedCtas = ['重试解析', '打开案件', '统一导出', '删除案件']
    const assertRecommended = (name?: string) => {
      for (const cta of recommendedCtas) {
        if (cta === name) expect(screen.getByRole('button', { name: cta })).toBeTruthy()
        else expect(screen.queryByRole('button', { name: cta })).toBeNull()
      }
    }
    const { unmount } = render(
      <MemoryRouter>
        <CaseCard
          shell={{ ...shell, lifecycle: 'parsing', report_available: false }}
          onRetry={vi.fn()}
          onCancel={vi.fn()}
          onDelete={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('解析中')).toBeTruthy()
    assertRecommended()
    unmount()

    render(
      <MemoryRouter>
        <CaseCard
          shell={{ ...shell, lifecycle: 'parse_failed_retryable', report_available: false }}
          onRetry={vi.fn()}
          onCancel={vi.fn()}
          onDelete={vi.fn()}
        />
      </MemoryRouter>,
    )
    assertRecommended('重试解析')
  })

  it.each([
    ['待处理', undefined, '打开案件'],
    ['待补盘号', 'disc_pending', '打开案件'],
    ['待导出', 'archive_complete', '统一导出'],
  ] as const)('shows %s with its expected recommended CTA', (status, completionStatus, cta) => {
    const phaseShell = completionStatus ? shell : { ...shell, lifecycle: 'review_ready' as const }
    render(
      <MemoryRouter>
        <CaseCard shell={phaseShell} completionStatus={completionStatus}
          onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} onExport={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText(status)).toBeTruthy()
    expect(screen.getByRole('button', { name: cta })).toBeTruthy()
    for (const other of ['重试解析', '打开案件', '统一导出', '删除案件'].filter(name => name !== cta)) {
      expect(screen.queryByRole('button', { name: other })).toBeNull()
    }
  })

  it('keeps open case available as a secondary action while awaiting export', () => {
    const onExport = vi.fn()
    const onDelete = vi.fn()
    render(
      <MemoryRouter>
        <CaseCard shell={shell} completionStatus="archive_complete"
          onRetry={vi.fn()} onCancel={vi.fn()} onDelete={onDelete} onExport={onExport} />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '统一导出' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '打开案件' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '更多操作' }))
    expect(screen.getAllByRole('menuitem').map(item => item.textContent)).toEqual(['打开案件', '删除案件'])
    const openCaseItem = screen.getByRole('menuitem', { name: '打开案件' })
    fireEvent.click(openCaseItem.querySelector('a')!)

    expect(screen.getByTestId('location').textContent)
      .toBe('/electronic-inspection/cases/case-SYNTHETIC-COMPLETION')
    expect(screen.getByRole('button', { name: '统一导出' })).toBeTruthy()
    expect(onExport).not.toHaveBeenCalled()
    expect(onDelete).not.toHaveBeenCalled()
  })

  it('keeps open case as the recommended CTA while background compression runs', () => {
    render(
      <MemoryRouter>
        <CaseCard shell={shell} archiveSummary={activeSummary} completionStatus="compressing"
          onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} onArchiveAction={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('处理中')).toBeTruthy()
    expect(screen.getByRole('button', { name: '打开案件' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '统一导出' })).toBeNull()
    expect(screen.queryByRole('button', { name: '删除案件' })).toBeNull()
  })

  it('does not let stale task details override archive_verified while completion data loads', () => {
    render(
      <MemoryRouter>
        <CaseCard shell={shell} archiveSummary={activeSummary}
          onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} onArchiveAction={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByText('正在确认归档结果……')).toBeTruthy()
    expect(screen.queryByText('正在写入并验证 Manifest')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '更多操作' }))
    expect(screen.queryByRole('menuitem', { name: '取消归档' })).toBeNull()
  })

  it('disables repeat export submission while the current request is loading', () => {
    const onExport = vi.fn()
    render(
      <MemoryRouter>
        <CaseCard shell={shell} completionStatus="archive_complete" exporting
          onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} onExport={onExport} />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: /统一导出/ }))
    expect(onExport).not.toHaveBeenCalled()
  })

  it('shows visible loading for an exported case during re-export', () => {
    render(
      <MemoryRouter>
        <CaseCard shell={{ ...shell, lifecycle: 'exported' }} exporting
          onRetry={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()} onExport={vi.fn()} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('button', { name: /loading.*再次导出/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '删除案件' })).toBeNull()
    expect((screen.getByRole('button', { name: '更多操作' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
