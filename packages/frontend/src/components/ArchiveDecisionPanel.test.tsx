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

  it('does not ask about compression for a failed parse', () => {
    render(<ArchiveDecisionPanel lifecycle="parse_failed_retryable" onImmediate={vi.fn()} onDeferred={vi.fn()} />)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
