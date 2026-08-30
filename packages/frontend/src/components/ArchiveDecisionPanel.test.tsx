import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ArchiveDecisionPanel } from './ArchiveDecisionPanel'

describe('ArchiveDecisionPanel', () => {
  it('asks for compression timing after successful parsing', () => {
    const onImmediate = vi.fn()
    const onDeferred = vi.fn()
    render(<ArchiveDecisionPanel lifecycle="review_ready" onImmediate={onImmediate} onDeferred={onDeferred} />)

    const buttons = screen.getAllByRole('button')
    fireEvent.click(buttons[0])
    fireEvent.click(buttons[1])
    expect(onImmediate).toHaveBeenCalledOnce()
    expect(onDeferred).toHaveBeenCalledOnce()
  })

  it('keeps deferred status visible without a progress indicator', () => {
    const onImmediate = vi.fn()
    render(<ArchiveDecisionPanel lifecycle="archive_deferred" onImmediate={onImmediate} onDeferred={vi.fn()} />)

    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.queryByRole('progressbar')).toBeNull()
    fireEvent.click(screen.getByRole('button'))
    expect(onImmediate).toHaveBeenCalledOnce()
  })

  it('shows the interruption reason and both explicit exit choices', () => {
    const onImmediate = vi.fn()
    const onDeferred = vi.fn()
    render(<ArchiveDecisionPanel lifecycle="archive_interrupted" onImmediate={onImmediate} onDeferred={onDeferred} />)
    expect(screen.getByText('上次压缩未完成')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '重新确认并立即压缩' }))
    fireEvent.click(screen.getByRole('button', { name: '稍后压缩' }))
    expect(onImmediate).toHaveBeenCalledOnce()
    expect(onDeferred).toHaveBeenCalledOnce()
  })

  it('shows background queue authority without a direct Legacy execution action', () => {
    render(<ArchiveDecisionPanel
      lifecycle="archive_queued"
      onImmediate={vi.fn()}
      onDeferred={vi.fn()}
    />)
    expect(screen.getByText('已进入等待归档')).toBeTruthy()
    expect(screen.getByText(/请勿修改、移动或删除源文件/)).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('keeps the source-file warning visible while WinRAR is running', () => {
    render(<ArchiveDecisionPanel lifecycle="archiving" onImmediate={vi.fn()} onDeferred={vi.fn()} />)
    expect(screen.getByText('正在读取源文件并压缩')).toBeTruthy()
    expect(screen.getByText(/RAR 完整性、分卷、案件所选文件哈希和清单/)).toBeTruthy()
    expect(screen.getByText(/不会为源目录执行额外的重复全量扫描/)).toBeTruthy()
  })

  it('does not ask about compression for a failed parse', () => {
    render(<ArchiveDecisionPanel lifecycle="parse_failed_retryable" onImmediate={vi.fn()} onDeferred={vi.fn()} />)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
