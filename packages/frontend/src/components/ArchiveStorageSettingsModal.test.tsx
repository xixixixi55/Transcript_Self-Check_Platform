import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import axios from 'axios'
import { describe, expect, it, vi } from 'vitest'
import { PlatformSidebar } from './PlatformSidebar'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

const customSettings = {
  active_directory: 'D:\\SYNTHETIC\\文枢归档工作区',
  configured_directory: 'D:\\SYNTHETIC\\文枢归档工作区',
  default_directory: 'C:\\SYNTHETIC\\archive',
  custom: true,
  valid: true,
  restart_required: false,
  error_code: null,
}

function renderSidebar(collapsed = false) {
  return render(
    <MemoryRouter>
      <PlatformSidebar collapsed={collapsed} onToggle={vi.fn()} />
    </MemoryRouter>,
  )
}

describe('archive storage settings', () => {
  it('沿用侧栏 footer 控件并展示重启后生效目录', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { data: {
      ...customSettings,
      active_directory: 'C:\\SYNTHETIC\\archive',
      restart_required: true,
    } } })
    const view = renderSidebar(true)

    const settingsButton = screen.getByRole('button', { name: '归档存储设置' })
    expect(settingsButton.closest('.platform-sidebar__footer')).toBeTruthy()
    fireEvent.click(settingsButton)

    expect(await screen.findByRole('dialog')).toBeTruthy()
    expect(screen.getByText('设置已保存，重启文枢后生效')).toBeTruthy()
    expect(screen.getByRole('button', { name: /选择目录/ })).toBeTruthy()
    expect(view.container.querySelector('.platform-sidebar__footer')).toBeTruthy()
  })

  it('恢复默认归档目录前要求确认', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { data: customSettings } })
    vi.mocked(axios.delete).mockResolvedValueOnce({ data: { data: {
      ...customSettings,
      configured_directory: customSettings.default_directory,
      custom: false,
      restart_required: true,
    } } })
    renderSidebar()
    fireEvent.click(screen.getByRole('button', { name: '归档存储设置' }))
    fireEvent.click(await screen.findByRole('button', { name: /恢复默认/ }))

    expect(screen.getByText('恢复默认归档目录？')).toBeTruthy()
    expect(axios.delete).not.toHaveBeenCalled()
    fireEvent.click(screen.getAllByRole('button', { name: /恢复默认/ }).at(-1)!)
    await waitFor(() => expect(axios.delete).toHaveBeenCalledTimes(1))
  })

  it('恢复默认失败后关闭确认框并在设置弹窗显示错误', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { data: customSettings } })
    vi.mocked(axios.delete).mockRejectedValueOnce({ response: { data: { detail: {
      message: 'SYNTHETIC/TEST/归档目录设置保存失败',
    } } } })
    renderSidebar()
    fireEvent.click(screen.getByRole('button', { name: '归档存储设置' }))
    fireEvent.click(await screen.findByRole('button', { name: /恢复默认/ }))
    fireEvent.click(screen.getAllByRole('button', { name: /恢复默认/ }).at(-1)!)

    expect(await screen.findByText('SYNTHETIC/TEST/归档目录设置保存失败')).toBeTruthy()
    await waitFor(() => expect(
      screen.queryByRole('dialog', { name: '恢复默认归档目录？' }),
    ).toBeNull())
  })
})
