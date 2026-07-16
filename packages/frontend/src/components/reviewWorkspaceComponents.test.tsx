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

  it('显示真实清单数量并支持定位章节', () => {
    const onNavigate = vi.fn()
    const items = [
      { id: 'one', sectionId: 'intro', sectionLabel: '一、绪论', fieldLabel: '检查地点', reason: '为空', severity: 'warning' as const },
      { id: 'two', sectionId: 'inspection', sectionLabel: '二、检查', fieldLabel: '检查方法', reason: '格式错误', severity: 'error' as const },
    ]
    render(<ReviewPendingSummary items={items} onNavigate={onNavigate} />)
    expect(screen.getByText('基础待核对 2 项')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /检查地点/ }))
    expect(onNavigate).toHaveBeenCalledWith('intro')
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
