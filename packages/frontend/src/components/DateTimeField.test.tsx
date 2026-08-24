import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { DateTimeField } from './DateTimeField'

describe('DateTimeField', () => {
  it('renders a date-only control and returns the existing date format', () => {
    const onChange = vi.fn()
    render(<DateTimeField label="委托时间" precision="date" value="2026年7月16日" onChange={onChange} />)

    const input = screen.getByLabelText('委托时间') as HTMLInputElement
    expect(input.value).toBe('2026-07-16')
    expect(input.type).toBe('date')
    fireEvent.change(input, { target: { value: '2024-02-29' } })
    expect(onChange).toHaveBeenCalledWith('2024年2月29日')
  })

  it('prompts for an empty date and clears the prompt after selection', () => {
    const onChange = vi.fn()
    const view = render(<DateTimeField label="委托时间" precision="date" value=""
      emptyHint="请选择委托日期。" onChange={onChange} />)

    expect(screen.getByText('请选择委托日期。')).toBeTruthy()
    const input = screen.getByLabelText('委托时间')
    expect(input.getAttribute('aria-describedby')).toBeTruthy()

    view.rerender(<DateTimeField label="委托时间" precision="date" value="2026年8月24日"
      emptyHint="请选择委托日期。" onChange={onChange} />)
    expect(screen.queryByText('请选择委托日期。')).toBeNull()
  })

  it('renders a minute-only range without a seconds control', () => {
    const onChange = vi.fn()
    render(<DateTimeField label="检查起止时间" precision="minute-range"
      value="2026年7月16日14点30分至2026年7月16日15点05分" onChange={onChange} />)

    const start = screen.getByLabelText('检查起止时间开始')
    const end = screen.getByLabelText('检查起止时间结束')
    expect(start.getAttribute('type')).toBe('datetime-local')
    expect(start.getAttribute('step')).toBe('60')
    expect((end as HTMLInputElement).value).toBe('2026-07-16T15:05')
    fireEvent.change(start, { target: { value: '2026-07-16T14:45' } })
    expect(onChange).toHaveBeenCalledWith('2026年7月16日14点45分至2026年7月16日15点05分')
  })
})
