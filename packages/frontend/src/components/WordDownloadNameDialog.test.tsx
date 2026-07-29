import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WordDownloadNameDialog } from './WordDownloadNameDialog'

vi.mock('antd', () => ({
  Input: ({ value, onChange, onPressEnter, ...props }: { value: string; onChange: (event: { target: { value: string } }) => void; onPressEnter?: () => void }) => (
    <input {...props} value={value} onChange={onChange} onKeyDown={event => { if (event.key === 'Enter') onPressEnter?.() }} />
  ),
  Modal: ({ open, title, children, onCancel, onOk }: { open: boolean; title: string; children: React.ReactNode; onCancel: () => void; onOk: () => void }) => open ? (
    <div role="dialog"><h1>{title}</h1>{children}<button onClick={onCancel}>取消</button><button onClick={onOk}>开始导出</button></div>
  ) : null,
}))

describe('WordDownloadNameDialog', () => {
  it('uses the current document number on every open and adds .docx once', () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    const view = render(<WordDownloadNameDialog open documentNumber="SYNTHETIC〔2026〕01号" onCancel={onCancel} onConfirm={onConfirm} />)

    const input = screen.getByLabelText('Word 下载文件名') as HTMLInputElement
    expect(input.value).toBe('SYNTHETIC〔2026〕01号.docx')
    fireEvent.change(input, { target: { value: '本次名称.docx.docx' } })
    fireEvent.click(screen.getByRole('button', { name: '开始导出' }))
    expect(onConfirm).toHaveBeenCalledWith('本次名称.docx')

    view.rerender(<WordDownloadNameDialog open={false} documentNumber="SYNTHETIC〔2026〕01号" onCancel={onCancel} onConfirm={onConfirm} />)
    view.rerender(<WordDownloadNameDialog open documentNumber="SYNTHETIC〔2026〕01号" onCancel={onCancel} onConfirm={onConfirm} />)
    expect((screen.getByLabelText('Word 下载文件名') as HTMLInputElement).value).toBe('SYNTHETIC〔2026〕01号.docx')
  })

  it('rejects empty and Windows-invalid names, and cancelling never requests an export', () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(<WordDownloadNameDialog open documentNumber="" onCancel={onCancel} onConfirm={onConfirm} />)

    fireEvent.click(screen.getByRole('button', { name: '开始导出' }))
    expect(screen.getByRole('alert').textContent).toContain('不能为空')
    expect(onConfirm).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Word 下载文件名'), { target: { value: 'invalid/name' } })
    fireEvent.click(screen.getByRole('button', { name: '开始导出' }))
    expect(screen.getByRole('alert').textContent).toContain('非法字符')
    expect(onConfirm).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(onCancel).toHaveBeenCalledOnce()
    expect(onConfirm).not.toHaveBeenCalled()
  })
})
