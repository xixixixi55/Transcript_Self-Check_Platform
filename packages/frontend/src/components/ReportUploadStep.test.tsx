import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import ReportUploadStep from './ReportUploadStep'

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false, media: query, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  })
})

function renderStep(overrides: Partial<React.ComponentProps<typeof ReportUploadStep>> = {}) {
  const onClearReportCache = vi.fn().mockResolvedValue({ cleared_count: 2 })
  render(
    <ReportUploadStep
      uploadMode="folder"
      onModeChange={vi.fn()}
      parsing={false}
      result={null}
      error={null}
      errorCode={null}
      onFolderUpload={vi.fn()}
      onArchiveUpload={vi.fn().mockResolvedValue(false)}
      onClearReportCache={onClearReportCache}
      clearingCache={false}
      {...overrides}
    />,
  )
  return onClearReportCache
}

describe('ReportUploadStep parsing cache controls', () => {
  it('requires confirmation and explains that the next parse is required', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const clear = renderStep()
    fireEvent.click(screen.getByRole('button', { name: '清空解析缓存' }))

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('清空后下次需要重新解析报告'))
    expect(clear).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  it('calls the clear action after confirmation and shows success feedback', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const clear = renderStep({
      cacheClearMessage: '已清理 2 条解析缓存。清空后下次需要重新解析报告。',
    })
    fireEvent.click(screen.getByRole('button', { name: '清空解析缓存' }))

    expect(clear).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/已清理 2 条解析缓存/)).toBeTruthy()
    vi.restoreAllMocks()
  })

  it('shows an actionable failure and prevents duplicate submission while busy', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const clear = renderStep({
      clearingCache: true,
      cacheClearError: '解析缓存清理失败，请重试。',
    })
    const clearButton = screen.getByRole('button', { name: /清空解析缓存/ }) as HTMLButtonElement
    expect(clearButton.disabled).toBe(true)
    expect(screen.getByText('解析缓存清理失败，请重试。')).toBeTruthy()
    fireEvent.click(clearButton)
    expect(clear).not.toHaveBeenCalled()
    confirm.mockRestore()
  })
})
