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
  })

  const renderPanel = (props: Partial<React.ComponentProps<typeof ArchiveCompletionPanel>> = {}) => {
    const onFirstDiscNumberChange = vi.fn()
    render(<ArchiveCompletionPanel
      lifecycle="review_ready"
      caseId="case-synthetic-disc-input"
      expectedRevision={1}
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

  it('does not expose a disc-number editor after the mapping is verified', () => {
    renderPanel({ lifecycle: 'archive_verified', parts: [{ disc_number: 'GP20260731-001' }] })
    expect(screen.queryByRole('textbox', { name: '首个光盘编号' })).toBeNull()
    expect(screen.getByText('归档完成')).toBeTruthy()
  })
})
