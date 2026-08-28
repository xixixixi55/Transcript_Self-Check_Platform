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
    FileWordOutlined: Icon,
    HomeOutlined: Icon,
    InfoCircleOutlined: Icon,
    LoadingOutlined: Icon,
    MenuFoldOutlined: Icon,
    MenuUnfoldOutlined: Icon,
    RollbackOutlined: Icon,
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
  const Button = ({ children, icon, onClick, disabled, loading, shape: _shape, size: _size, ...props }: any) => (
    <button {...props} onClick={onClick} disabled={disabled || loading}>{icon}{children}</button>
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

  it('使用必填空缺计算四部分进度，并将校验提醒单独展示', () => {
    const onNavigate = vi.fn()
    const onNavigateSection = vi.fn()
    const items = [
      { id: 'one', sectionId: 'review-section-introduction', targetId: 'place', sectionLabel: '一、绪论', fieldLabel: '检查地点', reason: '为空', severity: 'warning' as const, kind: 'required_missing' as const },
      { id: 'two', sectionId: 'review-section-inspection', targetId: 'method', sectionLabel: '二、检查', fieldLabel: '检查方法', reason: '格式错误', severity: 'error' as const, kind: 'validation' as const },
    ]
    render(<ReviewPendingSummary items={items} onNavigate={onNavigate} onNavigateSection={onNavigateSection} />)
    expect(screen.getByText('必填进度 3/4')).toBeTruthy()
    expect(screen.getByText('尚缺 1 个必填字段，另有 1 项校验提醒')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '一、绪论，缺少 1 项' }))
    expect(onNavigateSection).toHaveBeenCalledWith('review-section-introduction')
    fireEvent.click(screen.getByRole('button', { name: /检查地点/ }))
    expect(onNavigate).toHaveBeenCalledWith(items[0])
  })

  it('提供四部分右侧进度导航和窄屏展开入口', () => {
    const onNavigate = vi.fn()
    const items = [
      { id: 'one', sectionId: 'review-section-introduction', targetId: 'place', sectionLabel: '一、绪论', fieldLabel: '检查地点', reason: '为空', severity: 'warning' as const, kind: 'required_missing' as const },
    ]
    render(<ReviewPendingSummary variant="side" items={items} onNavigate={onNavigate} />)

    expect(screen.getByRole('complementary', { name: '审核进度导航' })).toBeTruthy()
    const trigger = screen.getByRole('button', { name: '必填进度 3/4，待核对 1 项' })
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
      { id: 'one', sectionId: 'review-section-introduction', targetId: 'place', sectionLabel: '一、绪论', fieldLabel: '检查地点', reason: '为空', severity: 'warning' as const, kind: 'required_missing' as const },
    ]
    render(<ReviewPendingSummary variant="side" items={items} onNavigate={vi.fn()} />)
    const dock = screen.getByRole('complementary', { name: '审核进度导航' })
    vi.spyOn(dock, 'getBoundingClientRect').mockReturnValue({
      left: 900, top: 300, right: 940, bottom: 412, width: 40, height: 112, x: 900, y: 300, toJSON: () => ({}),
    })
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1000 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 700 })
    const trigger = screen.getByRole('button', { name: '必填进度 3/4，待核对 1 项' })
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
    fireEvent.click(screen.getByRole('button', { name: '收起进度导航' }))
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    expect(dock.style.left).toBe('952px')
    expect(dock.style.top).toBe('500px')
    fireEvent.click(trigger)
    fireEvent.click(screen.getByRole('button', { name: '重置位置' }))
    expect(dock.style.left).toBe('')
    expect(dock.style.top).toBe('')
  })

  it('没有待核对项时仍显示四部分绿色进度', () => {
    render(<ReviewPendingSummary variant="side" items={[]} onNavigate={vi.fn()} />)
    expect(screen.getByRole('complementary', { name: '审核进度导航' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '必填进度 4/4，待核对 0 项' })).toBeTruthy()
    expect(screen.getByText('必填进度 4/4')).toBeTruthy()
    expect(screen.getAllByText('必填已齐')).toHaveLength(4)
  })

  it('检材完整性未确认时使用红色进度并阻止绪论完成', () => {
    const items = [{
      id: 'evidence-completeness', sectionId: 'review-section-introduction',
      targetId: 'review-target-evidence-completeness', sectionLabel: '一、绪论',
      fieldLabel: '检材完整性', reason: '请确认检材是否完整。',
      severity: 'error' as const, kind: 'confirmation_required' as const,
    }]
    const view = render(<ReviewPendingSummary variant="side" items={items} onNavigate={vi.fn()} />)

    expect(screen.getByRole('button', { name: '必填进度 3/4，待核对 1 项' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '必填进度 3/4，待核对 1 项' }))
    expect(screen.getByRole('button', { name: '一、绪论，待确认 1 项' })).toBeTruthy()
    expect(screen.getByText(/四部分必填字段均已填写，另有 1 项完整性待确认/)).toBeTruthy()
    expect(view.container.querySelector('.review-progress__bar--confirmation-pending')).toBeTruthy()
    expect(view.container.querySelector('.review-pending-dock--complete')).toBeNull()
  })

  it('四部分均有必填空缺时显示 0/4', () => {
    const sectionIds = ['review-section-document', 'review-section-introduction', 'review-section-inspection', 'review-section-archive']
    const items = sectionIds.map((sectionId, index) => ({
      id: `SYNTHETIC-${index}`, sectionId, targetId: `target-${index}`, sectionLabel: '合成章节',
      fieldLabel: `合成必填字段${index}`, reason: '为空', severity: 'warning' as const, kind: 'required_missing' as const,
    }))
    render(<ReviewPendingSummary items={items} onNavigate={vi.fn()} />)
    expect(screen.getByText('必填进度 0/4')).toBeTruthy()
    expect(screen.getByRole('progressbar', { name: '四部分必填进度' }).getAttribute('aria-valuenow')).toBe('0')
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

  it('保存中仍允许导出动作主动冲刷草稿', () => {
    const onSave = vi.fn()
    const onExport = vi.fn()
    render(<ReviewActionBar status="存在未导出修改" saveBusy onSave={onSave} onBack={vi.fn()} exporting={false} onExport={onExport} />)
    expect((screen.getByRole('button', { name: /保存当前修改/ }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: /导出 Word/ }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByRole('button', { name: '返回重新上传' }).textContent).toBe('')
    expect(screen.getByRole('button', { name: '保存当前修改' }).textContent).toBe('')
    expect(screen.getByRole('button', { name: '导出 Word' }).textContent).toBe('')
    expect(screen.getByText('存在未导出修改')).toBeTruthy()
  })

  it('在完整审核底栏区分返回引导与返回案件工作台', () => {
    const onReturnToGuided = vi.fn()
    const onBack = vi.fn()
    render(<ReviewActionBar status="尚未修改" saveBusy={false} exporting={false}
      backLabel="返回案件工作台" onReturnToGuided={onReturnToGuided}
      onSave={vi.fn()} onBack={onBack} onExport={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '返回引导模式' }))
    fireEvent.click(screen.getByRole('button', { name: '返回案件工作台' }))
    expect(onReturnToGuided).toHaveBeenCalledOnce()
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('保存状态明确说明当前页面状态而非服务器保存', () => {
    render(<ReviewSaveStatus status="当前页面修改已更新" />)
    expect(screen.getByText('当前页面修改已更新')).toBeTruthy()
    expect(screen.getByText('仅更新当前页面状态，未写入服务器')).toBeTruthy()
  })
})
