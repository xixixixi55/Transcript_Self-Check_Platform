import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { allPartsDiscMapped, resolveArchiveCompletionStatus } from '@biji/shared/utils'
import { ArchiveCompletionPanel } from './ArchiveCompletionPanel'

const mapping = vi.fn()

vi.mock('../hooks/useArchiveCompletion', () => ({
  resolveArchiveCompletionStatusForParts: (
    lifecycle: Parameters<typeof resolveArchiveCompletionStatus>[0],
    parts: { disc_number?: string | null }[] | null,
  ) => resolveArchiveCompletionStatus(lifecycle, allPartsDiscMapped(parts)),
  useArchiveCompletion: () => ({
    busy: false,
    error: null,
    mapping,
  }),
}))

describe('ArchiveCompletionPanel unified disc-number input', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mapping.mockResolvedValue({
      plan_row_revision: 3,
      parts: [{ disc_number: 'GP20260731-002' }],
    })
  })

  const renderPanel = (props: Partial<React.ComponentProps<typeof ArchiveCompletionPanel>> = {}) => {
    const onFirstDiscNumberChange = vi.fn()
    render(<ArchiveCompletionPanel
      lifecycle="review_ready"
      caseId="case-synthetic-disc-input"
      expectedRevision={1}
      planRowRevision={2}
      parts={null}
      firstDiscNumber="GP20260731-001"
      onFirstDiscNumberChange={onFirstDiscNumberChange}
      onCompleted={vi.fn()}
      {...props}
    />)
    return { onFirstDiscNumberChange }
  }

  it('updates the draft-bound value before compression starts', () => {
    const { onFirstDiscNumberChange } = renderPanel()
    fireEvent.change(screen.getByRole('textbox', { name: '首个光盘编号' }), {
      target: { value: 'GP20260731-002' },
    })
    expect(onFirstDiscNumberChange).toHaveBeenCalledWith('GP20260731-002')
    expect(mapping).not.toHaveBeenCalled()
  })

  it('keeps one complete input string for the new GP format', () => {
    const { onFirstDiscNumberChange } = renderPanel({
      firstDiscNumber: 'GP2026073102-001',
    })
    const input = screen.getByRole('textbox', { name: '首个光盘编号' }) as HTMLInputElement
    expect(input.value).toBe('GP2026073102-001')
    expect(input.placeholder).toBe('如 GP2026073102-01')
    expect(screen.getAllByRole('textbox')).toHaveLength(1)
    fireEvent.change(input, { target: { value: 'GP2026073199-001' } })
    expect(onFirstDiscNumberChange).toHaveBeenCalledWith('GP2026073199-001')
  })

  it('keeps the same draft-bound input during compression', () => {
    const { onFirstDiscNumberChange } = renderPanel({ lifecycle: 'archiving' })
    expect(screen.getByText(/压缩正在后台进行/)).toBeTruthy()
    fireEvent.change(screen.getByRole('textbox', { name: '首个光盘编号' }), {
      target: { value: 'GP20260731-003' },
    })
    expect(onFirstDiscNumberChange).toHaveBeenCalledWith('GP20260731-003')
  })

  it('prevents a read-only page from editing or submitting a pending mapping', () => {
    renderPanel({ lifecycle: 'archive_verified', parts: [{ disc_number: '' }], readOnly: true })
    const input = screen.getByRole('textbox', { name: '首个光盘编号' }) as HTMLInputElement
    const submit = screen.getByRole('button', { name: '提交盘号映射' }) as HTMLButtonElement
    expect(input.disabled).toBe(true)
    expect(submit.disabled).toBe(true)
    fireEvent.click(submit)
    expect(mapping).not.toHaveBeenCalled()
  })

  it('uses neutral GP/YP guidance before the archive medium is known', () => {
    const { onFirstDiscNumberChange } = renderPanel({
      archiveMedium: null,
      firstDiscNumber: 'YP20260413-01',
    })
    expect(screen.getByText('介质编号（可提前填写）')).toBeTruthy()
    expect(screen.getByText(/最终介质由压缩前归档总量决定/)).toBeTruthy()
    const input = screen.getByRole('textbox', { name: '介质编号' }) as HTMLInputElement
    expect(input.value).toBe('YP20260413-01')
    fireEvent.change(input, { target: { value: 'GP20260731-01' } })
    expect(onFirstDiscNumberChange).toHaveBeenCalledWith('GP20260731-01')
  })

  it('asks for one user hard-drive number for an oversized single volume', async () => {
    renderPanel({
      lifecycle: 'archive_verified',
      archiveMedium: 'hard_drive',
      parts: [{ disc_number: '' }],
      firstDiscNumber: 'YP20260413-01',
    })
    expect(screen.getByText('待补硬盘编号')).toBeTruthy()
    expect(screen.getByText(/一个超大单卷/)).toBeTruthy()
    const input = screen.getByRole('textbox', { name: '硬盘编号' }) as HTMLInputElement
    expect(input.value).toBe('YP20260413-01')
    fireEvent.click(screen.getByRole('button', { name: '提交硬盘编号' }))
    await vi.waitFor(() => {
      expect(mapping).toHaveBeenCalledWith(
        'case-synthetic-disc-input', 1, 2, 'YP20260413-01',
      )
    })
  })

  it('keeps the persisted first disc editable after the mapping is verified', async () => {
    const { onFirstDiscNumberChange } = renderPanel({
      lifecycle: 'archive_verified',
      parts: [{ disc_number: 'GP20260731-001' }],
      firstDiscNumber: '',
    })
    const input = screen.getByRole('textbox', { name: '首个光盘编号' }) as HTMLInputElement
    expect(input.value).toBe('GP20260731-001')
    fireEvent.change(input, { target: { value: 'GP20260731-002' } })
    fireEvent.click(screen.getByRole('button', { name: '更新盘号映射' }))
    expect(mapping).toHaveBeenCalledWith(
      'case-synthetic-disc-input', 1, 2, 'GP20260731-002',
    )
    await vi.waitFor(() => {
      expect(onFirstDiscNumberChange).toHaveBeenCalledWith('GP20260731-002')
    })
    expect(screen.getByText('归档完成')).toBeTruthy()
    expect(screen.getByText(/全部 RAR、文件哈希与盘号已对应完成/)).toBeTruthy()
  })

  it('allows an exported case to remap with the displayed plan revision', async () => {
    mapping
      .mockResolvedValueOnce({
        plan_row_revision: 7,
        parts: [{ disc_number: 'GP20260731-007' }],
      })
      .mockResolvedValueOnce({
        plan_row_revision: 8,
        parts: [{ disc_number: 'GP20260731-008' }],
      })
    renderPanel({
      lifecycle: 'exported',
      planRowRevision: 6,
      parts: [{ disc_number: 'GP20260731-005' }, { disc_number: 'GP20260731-006' }],
    })
    expect(screen.getByText('统一导出已完成；如需再次导出，请返回案件工作台。')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /再次导出|开始导出/ })).toBeNull()
    expect(screen.queryByText(/截图|PNG/)).toBeNull()
    fireEvent.change(screen.getByRole('textbox', { name: '首个光盘编号' }), {
      target: { value: 'GP20260731-007' },
    })
    fireEvent.click(screen.getByRole('button', { name: '更新盘号映射' }))
    await vi.waitFor(() => {
      expect(mapping).toHaveBeenCalledWith(
        'case-synthetic-disc-input', 1, 6, 'GP20260731-007',
      )
    })
    fireEvent.change(screen.getByRole('textbox', { name: '首个光盘编号' }), {
      target: { value: 'GP20260731-008' },
    })
    fireEvent.click(screen.getByRole('button', { name: '更新盘号映射' }))
    await vi.waitFor(() => {
      expect(mapping).toHaveBeenLastCalledWith(
        'case-synthetic-disc-input', 1, 7, 'GP20260731-008',
      )
    })
  })

  it('directs archive-complete cases to the workbench without an internal unified export action', () => {
    renderPanel({
      lifecycle: 'archive_verified',
      parts: [{ disc_number: 'GP20260731-001', size_bytes: 22_000_000_000 }],
    })
    expect(screen.getByText(/请返回案件工作台统一导出/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /再次导出|开始导出/ })).toBeNull()
  })
})
