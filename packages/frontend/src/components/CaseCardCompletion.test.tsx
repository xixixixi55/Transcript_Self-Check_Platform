import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import type { CaseShell } from '@biji/shared/types'
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
  it('shows the exported completion badge with the unified delete action', () => {
    const onDelete = vi.fn()
    render(
      <MemoryRouter>
        <CaseCard
          shell={{ ...shell, lifecycle: 'exported' }}
          completionStatus="exported"
          onRetry={vi.fn()}
          onCancel={vi.fn()}
          onDelete={onDelete}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText(/归档状态：已导出/)).toBeTruthy()
    fireEvent.click(screen.getByLabelText('更多操作'))
    expect(screen.queryByText('彻底删除')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /^删\s*除$/ }))
    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('shows disc-pending and archive-complete badges without an extra delete menu', () => {
    const { unmount } = render(
      <MemoryRouter>
        <CaseCard
          shell={shell}
          completionStatus="disc_pending"
          onRetry={vi.fn()}
          onCancel={vi.fn()}
          onDelete={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText(/归档状态：待补盘号/)).toBeTruthy()
    unmount()
    render(
      <MemoryRouter>
        <CaseCard
          shell={shell}
          completionStatus="archive_complete"
          onRetry={vi.fn()}
          onCancel={vi.fn()}
          onDelete={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText(/归档状态：归档完成/)).toBeTruthy()
    expect(screen.queryByText('彻底删除')).toBeNull()
  })
})
