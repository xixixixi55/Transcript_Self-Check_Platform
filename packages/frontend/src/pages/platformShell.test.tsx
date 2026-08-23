import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import axios from 'axios'
import { FileTextOutlined } from '@ant-design/icons'
import { PlatformShell } from '../components/PlatformShell'
import { PlatformSidebar } from '../components/PlatformSidebar'
import HomePage, { HomePageContent, type HomeAchievementItem } from './HomePage'
import { LegacyRedirect } from '../App'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

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
    expect(screen.getByText('笔录默认设置')).toBeTruthy()
    expect(screen.getByText('更多能力')).toBeTruthy()
    fireEvent.click(screen.getByText('更多能力').closest('.ant-menu-submenu-title') as HTMLElement)
    expect(screen.getAllByText('即将开放')).toHaveLength(1)
    expect(document.querySelector('.platform-sidebar .ant-menu-light')).toBeTruthy()
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
    const view = render(
      <MemoryRouter>
        <PlatformShell><div>页面内容</div></PlatformShell>
      </MemoryRouter>,
    )
    const sidebar = screen.getByRole('complementary')
    expect(sidebar.className).toContain('ant-layout-sider-collapsed')
    expect(screen.getByRole('button', { name: '展开导航' })).toBeTruthy()
    expect(screen.getByRole('main').contains(screen.getByText('页面内容'))).toBe(true)
    expect(screen.queryByRole('banner')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '展开导航' }))
    expect(view.container.querySelector('.ant-layout-sider-collapsed')).toBeNull()
    expect(screen.getByRole('button', { name: '收起导航' })).toBeTruthy()
  })

  it('折叠态提供图标名称，打开子菜单后关闭遮挡选项的提示', async () => {
    const view = render(
      <MemoryRouter>
        <PlatformSidebar collapsed onToggle={vi.fn()} />
      </MemoryRouter>,
    )
    const sidebar = screen.getByRole('complementary')
    expect(sidebar.className).toContain('ant-layout-sider-collapsed')
    expect(sidebar.getAttribute('style')).toContain('flex: 0 0 80px')
    expect(screen.getByRole('menuitem', { name: '首页' })).toBeTruthy()
    expect(view.container.querySelectorAll('.platform-sidebar__nav-icon')).toHaveLength(3)

    const homeIcon = view.container.querySelector('.platform-sidebar__nav-icon')
    expect(homeIcon).toBeTruthy()
    expect(homeIcon?.getAttribute('aria-label')).toBe('首页')
    expect(homeIcon?.querySelector('.anticon')?.closest('[aria-hidden="true"]')).toBeTruthy()

    const moduleTitle = view.container.querySelector('[aria-label="电子数据检查笔录"] .ant-menu-submenu-title')
    expect(moduleTitle).toBeTruthy()
    expect(moduleTitle?.getAttribute('aria-expanded')).toBe('false')
    const moduleIcon = moduleTitle?.querySelector('.platform-sidebar__nav-icon > span')
    expect(moduleIcon).toBeTruthy()
    fireEvent.mouseEnter(moduleIcon as Element)
    await screen.findByRole('tooltip', { name: '电子数据检查笔录' })
    fireEvent.click(moduleTitle as Element)
    expect(moduleTitle?.getAttribute('aria-expanded')).toBe('true')
    await waitFor(() => expect(screen.queryByRole('tooltip', { name: '电子数据检查笔录' })).toBeNull())
    expect(screen.getByText('案件工作台')).toBeTruthy()
    for (const label of ['案件工作台', '电子设备管理', '检查人员管理', '笔录模版管理', '笔录默认设置']) {
      expect(screen.getByText(label).closest('.ant-menu-item')?.getAttribute('title')).toBeNull()
    }
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

  it('从案件工作台点击折叠态首页图标可返回平台首页', () => {
    const view = render(
      <MemoryRouter initialEntries={['/electronic-inspection/workbench']}>
        <PlatformSidebar collapsed onToggle={vi.fn()} />
        <RedirectLocationProbe />
      </MemoryRouter>,
    )
    const homeIcon = view.container.querySelector('.platform-sidebar__nav-icon[aria-label="首页"]')
    expect(homeIcon).toBeTruthy()
    fireEvent.click(homeIcon as Element)
    expect(screen.getByTestId('redirected-location').textContent).toBe('/')
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

  it('笔录默认设置位于模板管理之后并可高亮', () => {
    render(
      <MemoryRouter initialEntries={['/electronic-inspection/defaults']}>
        <PlatformSidebar collapsed={false} onToggle={vi.fn()} />
      </MemoryRouter>,
    )
    const defaultLink = screen.getByRole('link', { name: '笔录默认设置' })
    expect(defaultLink.getAttribute('href')).toBe('/electronic-inspection/defaults')
    expect(defaultLink.closest('.ant-menu-item')?.className).toContain('ant-menu-item-selected')
    const labels = Array.from(document.querySelectorAll('.platform-sidebar .ant-menu-item'))
      .map(item => item.textContent?.trim())
    expect(labels.indexOf('笔录默认设置')).toBe(labels.indexOf('笔录模版管理') + 1)
  })
})

describe('platform home', () => {
  it('只展示已开放功能的成果占位，不重复 Sidebar 导航', () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>)
    expect(screen.getByRole('heading', { level: 1, name: '工作成果' })).toBeTruthy()
    expect(screen.getByRole('heading', { level: 2, name: '已开放功能' })).toBeTruthy()
    expect(screen.getByRole('heading', { level: 3, name: '电子数据检查笔录' })).toBeTruthy()
    expect(screen.getByText('累计成功处理案件')).toBeTruthy()
    expect(screen.getByText('近两周新增')).toBeTruthy()
    expect(screen.getByText('数据更新时间')).toBeTruthy()
    expect(screen.getAllByText('—')).toHaveLength(3)
    expect(screen.getByText('数据待接入')).toBeTruthy()
    expect(screen.queryByText('专业化勘查报告')).toBeNull()
    expect(document.querySelectorAll('.platform-home__achievement-card')).toHaveLength(1)
    expect(document.querySelector('.platform-home a, .platform-home button')).toBeNull()
  })

  function buildSyntheticHomeItems(availableCount: number): HomeAchievementItem[] {
    const items: HomeAchievementItem[] = []
    for (let index = 0; index < 6; index += 1) {
      const title = `SYNTHETIC 功能 ${index + 1}`
      if (index < availableCount) {
        items.push({
          key: `synthetic-available-${index + 1}`,
          icon: FileTextOutlined,
          title,
          status: 'available',
          metricLabel: `SYNTHETIC 累计成果 ${index + 1}`,
          unit: '件',
          achievement: { state: 'pending' },
        })
      } else {
        items.push({ key: `synthetic-coming-${index + 1}`, icon: FileTextOutlined, title, status: 'comingSoon' })
      }
    }
    return items
  }

  it.each([1, 2, 3])('按状态自然适配 %i 个成果模块', availableCount => {
    render(<MemoryRouter><HomePageContent items={buildSyntheticHomeItems(availableCount)} /></MemoryRouter>)
    const achievementGrid = document.querySelector('.platform-home__achievement-grid')
    expect(achievementGrid?.getAttribute('data-available-count')).toBe(String(availableCount))
    expect(achievementGrid?.className).toContain(`platform-home__achievement-grid--count-${availableCount}`)
    expect(document.querySelectorAll('.platform-home__achievement-card')).toHaveLength(availableCount)
    expect(screen.queryByText(`SYNTHETIC 功能 ${availableCount + 1}`)).toBeNull()
    expect(document.querySelector('.platform-home a, .platform-home button')).toBeNull()
  })

  it('模块状态改变后自然进入成果总览', () => {
    const view = render(<MemoryRouter><HomePageContent items={buildSyntheticHomeItems(1)} /></MemoryRouter>)
    expect(screen.queryByRole('heading', { level: 3, name: 'SYNTHETIC 功能 2' })).toBeNull()

    view.rerender(<MemoryRouter><HomePageContent items={buildSyntheticHomeItems(2)} /></MemoryRouter>)
    expect(screen.getByRole('heading', { level: 3, name: 'SYNTHETIC 功能 2' })
      .closest('.platform-home__achievement-card')).toBeTruthy()
  })

  it('展示已接入的准确成果数据和更新时间', () => {
    const items = buildSyntheticHomeItems(1)
    items[0] = {
      ...items[0],
      status: 'available',
      metricLabel: '累计成功处理案件',
      unit: '件',
      achievement: { state: 'ready', total: 12386, recent14d: 136, updatedAt: '2026-08-16 14:30' },
    }
    render(<MemoryRouter><HomePageContent items={items} /></MemoryRouter>)
    expect(screen.getByText('12,386')).toBeTruthy()
    expect(screen.getByText('+136')).toBeTruthy()
    expect(screen.getByText('2026-08-16 14:30')).toBeTruthy()
    expect(screen.getByText('数据已更新')).toBeTruthy()
  })

  it('只在统计明确返回零值时展示 0，并区分暂不可用状态', () => {
    const readyItems = buildSyntheticHomeItems(1)
    readyItems[0] = {
      ...readyItems[0],
      status: 'available',
      metricLabel: '累计成功处理案件',
      unit: '件',
      achievement: { state: 'ready', total: 0, recent14d: 0, updatedAt: '2026-08-16 14:30' },
    }
    const view = render(<MemoryRouter><HomePageContent items={readyItems} /></MemoryRouter>)
    expect(screen.getAllByText('0')).toHaveLength(2)

    const unavailableItems = buildSyntheticHomeItems(1)
    unavailableItems[0] = {
      ...unavailableItems[0],
      status: 'available',
      metricLabel: '累计成功处理案件',
      unit: '件',
      achievement: { state: 'unavailable' },
    }
    view.rerender(<MemoryRouter><HomePageContent items={unavailableItems} /></MemoryRouter>)
    expect(screen.getByText('统计暂时不可用')).toBeTruthy()
    expect(screen.getAllByText('—')).toHaveLength(3)
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
