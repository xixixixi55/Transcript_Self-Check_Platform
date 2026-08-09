import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ArchiveCompletionPanel } from './ArchiveCompletionPanel'

const mapping = vi.fn()

vi.mock('../hooks/useArchiveCompletion', () => ({
  useArchiveCompletion: () => ({
    busy: false,
    error: null,
    mapping,
    chooseDirectory: vi.fn(),
    exportBundle: vi.fn(),
  }),
}))

vi.mock('./WordDownloadNameDialog', () => ({ WordDownloadNameDialog: () => null }))

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
})
