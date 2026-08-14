import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import axios from 'axios'
import { PlatformShell } from '../components/PlatformShell'
import { PlatformSidebar } from '../components/PlatformSidebar'
import HomePage from './HomePage'
import { LegacyRedirect } from '../App'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))

function RedirectLocationProbe() {
  const location = useLocation()
  return <output data-testid="redirected-location">{location.pathname}{location.search}{location.hash}</output>
}

beforeAll(() => {
  vi.mocked(axios.get).mockResolvedValue({ data: { data: { items: [] } } })
  if (!window.matchMedia) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    })
  }
})

function getModuleMenuTitle() {
  const title = screen.getByText('电子数据检查笔录').closest('.ant-menu-submenu-title')
  if (!title) throw new Error('未找到电子数据检查笔录一级菜单行')
  return title as HTMLElement
}

function getModuleExpandedState() {
  const title = getModuleMenuTitle()
  return title.getAttribute('aria-expanded') || title.querySelector('[aria-expanded]')?.getAttribute('aria-expanded')
}

describe('platform shell navigation', () => {
  it('在业务子页面显示一级导航和展开的二级导航', () => {
    render(
      <MemoryRouter initialEntries={['/electronic-inspection/workbench']}>
        <PlatformSidebar collapsed={false} onToggle={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.getByText('首页')).toBeTruthy()
    expect(screen.getByText('电子数据检查笔录')).toBeTruthy()
    expect(screen.queryByText('模块首页')).toBeNull()
    expect(screen.getByRole('link', { name: '电子数据检查笔录' }).getAttribute('href')).toBe('/electronic-inspection/workbench')
    expect(screen.getByText('案件工作台')).toBeTruthy()
    expect(screen.queryByText('生成笔录')).toBeNull()
    expect(screen.getByText('电子设备管理')).toBeTruthy()
    expect(screen.getByText('笔录模版管理')).toBeTruthy()
    expect(screen.getAllByText('暂未开放')).toHaveLength(5)
  })

  it('支持主动收起和展开侧栏', () => {
    const onToggle = vi.fn()
    const view = render(
      <MemoryRouter>
        <PlatformSidebar collapsed={false} onToggle={onToggle} />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: '收起导航' }))
    expect(onToggle).toHaveBeenCalledTimes(1)

    view.rerender(
      <MemoryRouter>
        <PlatformSidebar collapsed onToggle={onToggle} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('button', { name: '展开导航' })).toBeTruthy()
  })

  it('所有主要页面共用同一个平台侧栏', () => {
    render(
      <MemoryRouter>
        <PlatformShell><div>页面内容</div></PlatformShell>
      </MemoryRouter>,
    )
    expect(screen.getByRole('complementary')).toBeTruthy()
    expect(screen.getByRole('main').contains(screen.getByText('页面内容'))).toBe(true)
    expect(screen.queryByRole('banner')).toBeNull()
  })

  it('点击一级菜单文字直接进入案件工作台', () => {
    render(
      <MemoryRouter initialEntries={['/electronic-inspection/workbench']}>
        <PlatformSidebar collapsed={false} onToggle={vi.fn()} />
        <RedirectLocationProbe />
      </MemoryRouter>,
    )
    const label = screen.getByText('电子数据检查笔录')
    fireEvent.click(label)
    expect(screen.getByTestId('redirected-location').textContent).toBe('/electronic-inspection/workbench')
  })

  it.each([
    ['图标区域', '.ant-menu-submenu-title .anticon'],
    ['箭头区域', '.ant-menu-submenu-arrow'],
  ])('点击%s可展开和收起一级菜单', (_region, selector) => {
    render(
      <MemoryRouter>
        <PlatformSidebar collapsed={false} onToggle={vi.fn()} />
      </MemoryRouter>,
    )
    const title = getModuleMenuTitle()
    const target = title.querySelector(selector)
    expect(target).toBeTruthy()
    expect(getModuleExpandedState()).toBe('false')
    fireEvent.click(target as Element)
    expect(getModuleExpandedState()).toBe('true')
    fireEvent.click(target as Element)
    expect(getModuleExpandedState()).toBe('false')
  })

  it('点击一级菜单整行空白区域可展开和收起', () => {
    render(
      <MemoryRouter>
        <PlatformSidebar collapsed={false} onToggle={vi.fn()} />
      </MemoryRouter>,
    )
    const title = getModuleMenuTitle()
    expect(getModuleExpandedState()).toBe('false')
    fireEvent.click(title)
    expect(getModuleExpandedState()).toBe('true')
    fireEvent.click(title)
    expect(getModuleExpandedState()).toBe('false')
  })

  it('一级菜单支持 Enter 和 Space，并同步 aria-expanded', () => {
    render(
      <MemoryRouter>
        <PlatformSidebar collapsed={false} onToggle={vi.fn()} />
      </MemoryRouter>,
    )
    const title = getModuleMenuTitle()
    expect(getModuleExpandedState()).toBe('false')
    fireEvent.keyDown(title, { key: 'Enter', code: 'Enter', keyCode: 13 })
    expect(getModuleExpandedState()).toBe('true')
    fireEvent.keyDown(title, { key: ' ', code: 'Space', keyCode: 32 })
    expect(getModuleExpandedState()).toBe('false')
  })

  it('二级菜单链接可进入功能，当前页面保持父级展开并高亮子项', () => {
    render(
      <MemoryRouter initialEntries={['/electronic-inspection/devices']}>
        <PlatformSidebar collapsed={false} onToggle={vi.fn()} />
      </MemoryRouter>,
    )
    const deviceLink = screen.getByRole('link', { name: '电子设备管理' })
    expect(deviceLink.getAttribute('href')).toBe('/electronic-inspection/devices')
    expect(getModuleExpandedState()).toBe('true')
    expect(deviceLink.closest('.ant-menu-item')?.className).toContain('ant-menu-item-selected')
  })

  it('模板管理与检查人员管理处于同级并可高亮', () => {
    render(
      <MemoryRouter initialEntries={['/electronic-inspection/templates']}>
        <PlatformSidebar collapsed={false} onToggle={vi.fn()} />
      </MemoryRouter>,
    )
    const templateLink = screen.getByRole('link', { name: '笔录模版管理' })
    expect(templateLink.getAttribute('href')).toBe('/electronic-inspection/templates')
    const templateItem = templateLink.closest('.ant-menu-item')
    expect(templateItem?.className).toContain('ant-menu-item-selected')
    expect(templateItem?.querySelector('.ant-menu-item-icon')).toBeNull()
  })
})

describe('platform home', () => {
  it('只将已开放功能作为可进入入口', () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>)
    expect(screen.getByText('电子数据检查文书辅助平台')).toBeTruthy()
    expect(document.querySelectorAll('a[href="/electronic-inspection/workbench"]')).toHaveLength(1)
    expect(screen.getAllByText('该功能暂未开放')).toHaveLength(5)
    expect(screen.getAllByText('暂未开放')).toHaveLength(5)
  })
})

describe('legacy routes', () => {
  it('电子数据检查入口默认重定向到案件工作台并保留参数', () => {
    render(
      <MemoryRouter initialEntries={['/electronic-inspection?case=1#tasks']}>
        <Routes>
          <Route path="/electronic-inspection" element={<LegacyRedirect to="/electronic-inspection/workbench" />} />
          <Route path="/electronic-inspection/workbench" element={<RedirectLocationProbe />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByTestId('redirected-location').textContent).toBe('/electronic-inspection/workbench?case=1#tasks')
  })

  it('重定向旧生成地址并保留查询参数和 hash', () => {
    render(
      <MemoryRouter initialEntries={['/generate?case=1#review']}>
        <Routes>
          <Route path="/generate" element={<LegacyRedirect to="/electronic-inspection/workbench" />} />
          <Route path="/electronic-inspection/workbench" element={<RedirectLocationProbe />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByTestId('redirected-location').textContent).toBe('/electronic-inspection/workbench?case=1#review')
  })

  it('重定向旧设备地址', () => {
    render(
      <MemoryRouter initialEntries={['/devices?from=legacy']}>
        <Routes>
          <Route path="/devices" element={<LegacyRedirect to="/electronic-inspection/devices" />} />
          <Route path="/electronic-inspection/devices" element={<RedirectLocationProbe />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByTestId('redirected-location').textContent).toBe('/electronic-inspection/devices?from=legacy')
  })
})
