import React from 'react'
import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useReviewWorkspaceShortcuts } from './useReviewWorkspaceShortcuts'

function ShortcutHarness({ onSave, onClose, previewOpen }: { onSave: () => void; onClose: () => void; previewOpen: boolean }) {
  useReviewWorkspaceShortcuts({ onSave, onClosePreview: onClose, previewOpen })
  return <input aria-label="字段" />
}

describe('useReviewWorkspaceShortcuts', () => {
  it('Ctrl+S 更新页面状态，预览打开时 Esc 关闭 Drawer', () => {
    const onSave = vi.fn()
    const onClose = vi.fn()
    render(<ShortcutHarness onSave={onSave} onClose={onClose} previewOpen />)
    fireEvent.keyDown(window, { key: 's', ctrlKey: true })
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('字段编辑状态下 Esc 不关闭预览', () => {
    const onClose = vi.fn()
    const view = render(<ShortcutHarness onSave={vi.fn()} onClose={onClose} previewOpen />)
    const input = view.getByLabelText('字段')
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })
})
