import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CaseSaveStatusPanel } from './CaseSaveStatusPanel'

vi.mock('antd', () => ({
  Alert: ({ message, description, action }: { message: string; description: string; action?: React.ReactNode }) => <div><strong>{message}</strong><span>{description}</span>{action}</div>,
  Button: ({ children }: { children: React.ReactNode }) => <button>{children}</button>,
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

describe('CaseSaveStatusPanel', () => {
  it('distinguishes a saved draft from a failed shared-default update', () => {
    render(<CaseSaveStatusPanel
      draft={{ status: 'saved', revision: 4 }}
      sharedDefaults={{ status: 'failed', errorCode: 'SYNTHETIC_DEFAULT_FAILURE' }}
      onRetry={vi.fn()}
      onLoadServer={vi.fn()}
    />)
    expect(screen.getByText('草稿已保存，共享默认值更新失败。')).toBeTruthy()
    expect(screen.getByText('当前案件已经保存；请重新修改相关共享字段后，再通过“保存修改”重试。')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '重试保存' })).toBeNull()
  })
})
