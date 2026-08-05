import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CaseWorkbenchDirectoryPickerCard } from './CaseWorkbenchDirectoryPickerCard'

describe('CaseWorkbenchDirectoryPickerCard', () => {
  it('presents a prominent report-directory action without a browser upload input', () => {
    const onClick = vi.fn()
    render(<CaseWorkbenchDirectoryPickerCard onClick={onClick} />)

    expect(screen.getByRole('button', { name: '上传报告目录' })).toBeTruthy()
    expect(screen.getByText('点击选择本机报告文件夹并立即解析')).toBeTruthy()
    expect(document.querySelector('input[type="file"]')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '上传报告目录' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('disables the card while the native picker request is pending', () => {
    render(<CaseWorkbenchDirectoryPickerCard loading onClick={vi.fn()} />)

    expect((screen.getByRole('button', { name: '上传报告目录' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('正在打开本机选择器…')).toBeTruthy()
  })
})
