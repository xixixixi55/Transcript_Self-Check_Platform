import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import type { CaseShell } from '@biji/shared/types'
import { CaseCard } from './CaseCard'

const shell: CaseShell = {
  schema_version: 1,
  case_id: 'case-SYNTHETIC-DELETE',
  case_name: 'SYNTHETIC/TEST case',
  case_summary: 'SYNTHETIC/TEST summary',
  source_id: 'source-SYNTHETIC-DELETE',
  parse_task_id: 'parse-SYNTHETIC-DELETE',
  lifecycle: 'review_ready',
  report_available: true,
  revision: 1,
  created_at: '2026-07-30T08:00:00Z',
  updated_at: '2026-07-30T11:00:00Z',
}

describe('CaseCard deletion action', () => {
  it('exposes deletion as an independent card action', () => {
    const onDelete = vi.fn()
    render(<MemoryRouter><CaseCard position={1} shell={shell} onRetry={vi.fn()} onCancel={vi.fn()} onDelete={onDelete} /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: /^删\s*除$/ }))
    expect(onDelete).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: '更多操作' }))
    expect(screen.queryByRole('menuitem', { name: '删除' })).toBeNull()
  })
})
