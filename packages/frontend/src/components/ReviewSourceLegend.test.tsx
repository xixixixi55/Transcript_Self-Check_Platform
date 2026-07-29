import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ReviewSourceLegend } from './ReviewSourceLegend'

vi.mock('antd', () => ({
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tag: ({ children, color }: { children: React.ReactNode; color?: string }) => <span data-color={color || 'none'}>{children}</span>,
  Typography: { Text: ({ children }: { children: React.ReactNode }) => <span>{children}</span> },
}))

describe('ReviewSourceLegend', () => {
  it('uses source text and a textual pending confirmation explanation', () => {
    render(<ReviewSourceLegend />)

    expect(screen.getByText('报告解析')).toBeTruthy()
    expect(screen.getByText('人工修改').getAttribute('data-color')).toBe('blue')
    expect(screen.getByText('系统默认值')).toBeTruthy()
    expect(screen.getByText('待人工确认').getAttribute('data-color')).toBe('orange')
    expect(screen.getByText(/不会写入 Word/)).toBeTruthy()
  })
})
