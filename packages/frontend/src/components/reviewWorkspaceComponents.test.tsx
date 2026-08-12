import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ReportWorkspaceShell } from './ReportWorkspaceShell'
import { ReviewActionBar } from './ReviewActionBar'
import { ReviewPendingSummary } from './ReviewPendingSummary'
import { ReviewPreviewDrawer } from './ReviewPreviewDrawer'
import { ReviewSection } from './ReviewSection'
import { ReviewSaveStatus } from './ReviewSaveStatus'
import type { InspectionReport } from '@biji/shared/types'
import { REVIEW_REVEAL_TARGET_EVENT } from '../hooks/useReviewChecklist'

vi.mock('react-router-dom', () => ({ Link: ({ children }: { children: React.ReactNode }) => <a href="/">{children}</a> }))
vi.mock('@ant-design/icons', () => {
  const Icon = () => <span aria-hidden="true" />
  return {
    ApartmentOutlined: Icon,
    CheckCircleOutlined: Icon,
    DownloadOutlined: Icon,
    EditOutlined: Icon,
    ExclamationCircleOutlined: Icon,
    EyeOutlined: Icon,
    FileSearchOutlined: Icon,
    FileTextOutlined: Icon,
    HomeOutlined: Icon,
    InfoCircleOutlined: Icon,
    LoadingOutlined: Icon,
    MenuFoldOutlined: Icon,
    MenuUnfoldOutlined: Icon,
    SaveOutlined: Icon,
    SafetyCertificateOutlined: Icon,
    WarningOutlined: Icon,
  }
})
vi.mock('antd', () => {
  const Layout = ({ children }: { children: React.ReactNode }) => <div>{children}</div>
  const Sider = ({ children }: { children: React.ReactNode }) => <aside>{children}</aside>
  const Content = ({ children }: { children: React.ReactNode }) => <main>{children}</main>
  Layout.Sider = Sider
  Layout.Content = Content
  const Menu = ({ items = [] }: { items?: { key: string; label: React.ReactNode; disabled?: boolean }[] }) => (
    <nav>{items.map(item => <div key={item.key} aria-disabled={item.disabled}>{item.label}</div>)}</nav>
  )
  const Button = ({ children, onClick, disabled, loading, ...props }: any) => (
    <button {...props} onClick={onClick} disabled={disabled || loading}>{children}</button>
  )
  const Descriptions = ({ children }: { children: React.ReactNode }) => <div>{children}</div>
  Descriptions.Item = ({ children, label }: { children: React.ReactNode; label: string }) => <div>{label}:{children}</div>
  return {
    Alert: ({ message, description }: { message: React.ReactNode; description?: React.ReactNode }) => <div>{message}{description}</div>,
    Button,
    ConfigProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Descriptions,
    Drawer: ({ open, title, children, onClose }: any) => open ? (
      <div role="dialog"><h2>{title}</h2><button onClick={onClose}>关闭预览</button>{children}</div>
    ) : null,
    Layout,
    Menu,
    Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Typography: {
      Paragraph: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
      Text: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
      Title: ({ children }: { children: React.ReactNode }) => <h3>{children}</h3>,
    },
  }
})

const report: InspectionReport = {
  title: '电子数据检查笔录',
  document_number: 'SYN-TEST〔2026〕001号',
  case_number: '2026-001',
  introduction: {
    entrust_unit: '单位', entrust_persons: ['人员'], entrust_time: '2026年7月16日', case_summary: '案件摘要',
    evidence_list: [], inspection_requirement: '要求', inspection_time_range: '2026年7月16日10点00分至2026年7月16日11点00分',
    inspectors: [], inspection_place: '地点',
  },
  inspection: {
    method: '方法', hardware_device: '设备', software_tools: [], process_steps: [],
    result: { evidence_number: '1', software_name: '工具', software_version: '1', data_summary: '摘要', rar_filename: 'a.rar', md5_hash: 'md5', file_size: '1MB' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '1' },
}

describe('review workspace components', () => {
  it('审核内容外壳不再渲染独立平台导航', () => {
    render(<ReportWorkspaceShell><div>工作区</div></ReportWorkspaceShell>)
    expect(screen.getByText('工作区')).toBeTruthy()
    expect(screen.queryByText('首页')).toBeNull()
  })

  it('支持折叠章节并保持可访问状态', () => {
    render(<ReviewSection id="test-section" title="一、绪论"><div>章节内容</div></ReviewSection>)
    const header = screen.getByRole('button', { name: /一、绪论/ })
    expect(header.getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(header)
    expect(header.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByText('章节内容')).toBeNull()
  })

  it('定位事件会先展开已折叠章节', () => {
    render(<ReviewSection id="test-section" title="一、绪论" defaultOpen={false}><div>章节内容</div></ReviewSection>)
    expect(screen.queryByText('章节内容')).toBeNull()
    fireEvent(window, new CustomEvent(REVIEW_REVEAL_TARGET_EVENT, { detail: { sectionId: 'test-section' } }))
    expect(screen.getByText('章节内容')).toBeTruthy()
  })

  it('显示真实清单数量并支持定位章节', () => {
    const onNavigate = vi.fn()
    const items = [
      { id: 'one', sectionId: 'intro', targetId: 'place', sectionLabel: '一、绪论', fieldLabel: '检查地点', reason: '为空', severity: 'warning' as const },
      { id: 'two', sectionId: 'inspection', targetId: 'method', sectionLabel: '二、检查', fieldLabel: '检查方法', reason: '格式错误', severity: 'error' as const },
    ]
    render(<ReviewPendingSummary items={items} onNavigate={onNavigate} />)
    expect(screen.getByText('基础待核对 2 项')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /检查地点/ }))
    expect(onNavigate).toHaveBeenCalledWith(items[0])
  })

  it('有待核对项时提供右侧导航和窄屏展开入口', () => {
    const onNavigate = vi.fn()
    const items = [
      { id: 'one', sectionId: 'intro', targetId: 'place', sectionLabel: '一、绪论', fieldLabel: '检查地点', reason: '为空', severity: 'warning' as const },
    ]
    render(<ReviewPendingSummary variant="side" items={items} onNavigate={onNavigate} />)

    expect(screen.getByRole('complementary', { name: '待核对导航' })).toBeTruthy()
    const trigger = screen.getByRole('button', { name: '待核对 1' })
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(trigger)
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: /检查地点/ }))
    expect(onNavigate).toHaveBeenCalledWith(items[0])
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
  })

  it('可直接拖动收起状态的待核对入口，且拖动不会误展开', () => {
    Object.defineProperty(window, 'PointerEvent', { configurable: true, value: MouseEvent })
    const items = [
      { id: 'one', sectionId: 'intro', targetId: 'place', sectionLabel: '一、绪论', fieldLabel: '检查地点', reason: '为空', severity: 'warning' as const },
    ]
    render(<ReviewPendingSummary variant="side" items={items} onNavigate={vi.fn()} />)
    const dock = screen.getByRole('complementary', { name: '待核对导航' })
    vi.spyOn(dock, 'getBoundingClientRect').mockReturnValue({
      left: 900, top: 300, right: 940, bottom: 412, width: 40, height: 112, x: 900, y: 300, toJSON: () => ({}),
    })
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1000 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 700 })
    const trigger = screen.getByRole('button', { name: '待核对 1' })
    fireEvent.pointerDown(trigger, { button: 0, pointerId: 1, clientX: 910, clientY: 310 })
    fireEvent.pointerMove(trigger, { pointerId: 1, clientX: 2000, clientY: 2000 })
    fireEvent.pointerUp(trigger, { pointerId: 1 })
    fireEvent.click(trigger)
    expect(dock.style.left).toBe('952px')
    expect(dock.style.top).toBe('500px')
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(trigger)
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    expect(dock.style.left).toBe('952px')
    expect(dock.style.top).toBe('500px')
    fireEvent.click(screen.getByRole('button', { name: '收起待核对项' }))
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    expect(dock.style.left).toBe('952px')
    expect(dock.style.top).toBe('500px')
    fireEvent.click(trigger)
    fireEvent.click(screen.getByRole('button', { name: '重置位置' }))
    expect(dock.style.left).toBe('')
    expect(dock.style.top).toBe('')
  })

  it('没有待核对项时不显示右侧导航或悬浮入口', () => {
    render(<ReviewPendingSummary variant="side" items={[]} onNavigate={vi.fn()} />)
    expect(screen.queryByRole('complementary', { name: '待核对导航' })).toBeNull()
    expect(screen.queryByRole('button', { name: /待核对/ })).toBeNull()
  })

  it('预览 Drawer 默认关闭，打开后可关闭', () => {
    const onClose = vi.fn()
    const view = render(<ReviewPreviewDrawer open={false} report={report} onClose={onClose} />)
    expect(screen.queryByRole('dialog')).toBeNull()
    view.rerender(<ReviewPreviewDrawer open report={report} onClose={onClose} />)
    expect(screen.getByRole('dialog').textContent).toContain('非最终 Word 版式预览')
    fireEvent.click(screen.getByRole('button', { name: '关闭预览' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('保存和导出处理中会防止重复触发', () => {
    const onSave = vi.fn()
    const onExport = vi.fn()
    render(<ReviewActionBar status="存在未导出修改" saveBusy onSave={onSave} onBack={vi.fn()} exporting onExport={onExport} />)
    expect((screen.getByRole('button', { name: /保存当前修改/ }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: /导出 Word/ }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('存在未导出修改')).toBeTruthy()
  })

  it('保存状态明确说明当前页面状态而非服务器保存', () => {
    render(<ReviewSaveStatus status="当前页面修改已更新" />)
    expect(screen.getByText('当前页面修改已更新')).toBeTruthy()
    expect(screen.getByText('仅更新当前页面状态，未写入服务器')).toBeTruthy()
  })
})
