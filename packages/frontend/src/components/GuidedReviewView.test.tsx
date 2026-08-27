import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { InspectionReport } from '@biji/shared/types'
import { describe, expect, it, vi } from 'vitest'
import type { GuidedReviewAction, GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'
import { GuidedReviewCard } from './GuidedReviewCard'
import { GuidedReviewView } from './GuidedReviewView'

const history: GuidedReviewHistoryItem[] = [
  { id: 'SYNTHETIC-HISTORY-1', tone: 'complete', title: '报告内容已自动识别', detail: '已从合成报告整理文号。' },
]
const documentAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-DOCUMENT', kind: 'pending_item', title: '请输入文号', description: '当前必填字段为空。',
  pendingItem: {
    id: 'SYNTHETIC-PENDING-DOCUMENT', sectionId: 'review-section-document',
    targetId: 'review-target-document-number', sectionLabel: '文书信息', fieldLabel: '文号',
    reason: '当前必填字段为空。', severity: 'warning', kind: 'required_missing',
  },
}
const waitingAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-WAITING', kind: 'waiting', title: '请稍候，正在生成压缩分卷',
  description: '后台任务仍在运行，可继续处理其他待办。',
}

const report: InspectionReport = {
  title: '电子数据检查笔录', document_number: '',
  introduction: {
    entrust_unit: 'SYNTHETIC-UNIT', entrust_persons: ['SYNTHETIC-PERSON'], entrust_time: '2026年08月25日',
    case_summary: 'SYNTHETIC SUMMARY', evidence_list: [], inspection_requirement: 'SYNTHETIC REQUIREMENT',
    inspection_time_range: '2026年08月25日09时00分至2026年08月25日10时00分', inspectors: [], inspection_place: 'SYNTHETIC-PLACE',
  },
  inspection: {
    method: 'SYNTHETIC-METHOD', hardware_device: 'SYNTHETIC-HARDWARE', software_tools: [], process_steps: [],
    result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
}

describe('GuidedReviewView', () => {
  it('keeps full history above the current conversation while exposing global review controls', () => {
    const selectAction = vi.fn()
    const updateReport = vi.fn()
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[documentAction, waitingAction]}
      hasResponse
      onSelectAction={selectAction}
      summary={<div>SYNTHETIC ORGANIZED SUMMARY</div>}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    >
      <GuidedReviewCard action={documentAction} report={report} updateReport={updateReport} readOnly={false} />
    </GuidedReviewView>)

    const historyRegion = screen.getByRole('region', { name: '历史处理轨迹' })
    const conversationRegion = screen.getByRole('region', { name: '当前对话' })
    expect(historyRegion.compareDocumentPosition(conversationRegion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByRole('button', { name: /历史处理轨迹/ })).toBeNull()
    expect(screen.getByText('报告内容已自动识别')).toBeTruthy()
    expect(screen.getByText('獬豸助手')).toBeTruthy()
    expect(screen.getByText('1 项待处理')).toBeTruthy()
    expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent).toContain('请输入文号')
    expect(screen.getByRole('group', { name: '你的回复' })).toBeTruthy()
    expect(screen.getByText('其他操作')).toBeTruthy()
    const mascot = view.container.querySelector<HTMLImageElement>('.guided-review-conversation__mascot img')
    const conversationBody = view.container.querySelector('.guided-review-conversation__body')
    const conversationContent = view.container.querySelector('.guided-review-conversation__content')
    const conversationUtilities = view.container.querySelector('.guided-review-conversation__utilities')
    expect(conversationBody?.querySelector(':scope > .guided-review-conversation__mascot img')).toBe(mascot)
    expect(conversationBody?.querySelector(':scope > .guided-review-conversation__content')).toBe(conversationContent)
    expect(conversationContent?.contains(mascot)).toBe(false)
    expect(conversationBody?.contains(conversationUtilities)).toBe(false)
    expect(mascot?.getAttribute('src')).toContain('xiezhi-assistant.png')
    fireEvent.error(mascot!)
    expect(view.container.querySelector('.anticon-safety-certificate')).toBeTruthy()

    const pendingButton = screen.getByRole('button', { name: '查看全部当前事项（2）' })
    const summaryButton = screen.getByRole('button', { name: '查看已整理信息' })
    expect(pendingButton.getAttribute('aria-controls')).toBe('guided-review-pending-panel')
    expect(summaryButton.getAttribute('aria-controls')).toBe('guided-review-summary-panel')
    fireEvent.click(pendingButton)
    expect(screen.getByLabelText('全部当前事项').id).toBe('guided-review-pending-panel')
    expect(screen.getByRole('button', { name: /请输入文号.*当前/ }).getAttribute('aria-current')).toBe('true')
    expect(screen.getByRole('button', { name: /请稍候，正在生成压缩分卷.*后台中/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /请稍候，正在生成压缩分卷/ }))
    expect(selectAction).toHaveBeenCalledWith(waitingAction.id)

    fireEvent.click(summaryButton)
    expect(screen.getByLabelText('已整理信息').id).toBe('guided-review-summary-panel')
    expect(screen.getByText('SYNTHETIC ORGANIZED SUMMARY')).toBeTruthy()
    expect(updateReport).not.toHaveBeenCalled()

    fireEvent.change(screen.getByRole('textbox', { name: '文号' }), { target: { value: 'SYN-TEST〔2026〕009号' } })
    expect(updateReport).toHaveBeenCalledWith('document_number', 'SYN-TEST〔2026〕009号')
  })

  it('renders empty history and waiting content without inventing percentage progress', () => {
    render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={[]}
      currentAction={waitingAction}
      allActions={[waitingAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    expect(screen.getByText('等待形成轨迹')).toBeTruthy()
    expect(screen.getByText('办理轨迹会随案件现有事实逐步形成。')).toBeTruthy()
    expect(screen.getByText('请稍候，正在生成压缩分卷')).toBeTruthy()
    expect(screen.getByText('后台处理中')).toBeTruthy()
    expect(screen.getAllByText('后台任务仍在运行，可继续处理其他待办。')).toHaveLength(1)
    expect(screen.queryByText(/30%|问题\s*\d+\s*\/\s*\d+/)).toBeNull()
  })

  it('confirms text input only with an unmodified Enter outside IME composition', () => {
    const confirmCurrentAction = vi.fn()
    render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={{ ...documentAction, advanceOnEnter: true }}
      allActions={[{ ...documentAction, advanceOnEnter: true }]}
      hasResponse
      onSelectAction={vi.fn()}
      onConfirmCurrentAction={confirmCurrentAction}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    const input = screen.getByRole('textbox', { name: '文号' })
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(confirmCurrentAction).not.toHaveBeenCalled()

    fireEvent.keyDown(input, { key: 'Enter' })
    expect(confirmCurrentAction).toHaveBeenCalledTimes(1)
  })

  it('shows a session-only user reply and assistant handoff after an action is completed', async () => {
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[documentAction, waitingAction]}
      hasResponse
      onSelectAction={vi.fn()}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={waitingAction}
      allActions={[waitingAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    await waitFor(() => expect(screen.getByLabelText('上一轮办理结果')).toBeTruthy())
    expect(screen.getByText('文号已填写')).toBeTruthy()
    expect(screen.getByText('已确认：文号已填写。后台任务还在继续，我会在这里同步进展。')).toBeTruthy()
    expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent).toContain('请稍候，正在生成压缩分卷')

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-OTHER-CASE"
      history={history}
      currentAction={waitingAction}
      allActions={[waitingAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)
    await waitFor(() => expect(screen.queryByLabelText('上一轮办理结果')).toBeNull())
  })

  it('anchors the current conversation by default and preserves history reading when records append', () => {
    let conversationOffset = 320
    const boundingRect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const scrollTop = this.parentElement?.classList.contains('guided-review-scroll')
        ? this.parentElement.scrollTop
        : 0
      return { top: this.classList.contains('guided-review-conversation') ? conversationOffset - scrollTop : 0 } as DOMRect
    })

    try {
      const renderView = (items: GuidedReviewHistoryItem[]) => <GuidedReviewView
        conversationKey="SYNTHETIC-CASE"
        history={items}
        currentAction={documentAction}
        allActions={[documentAction]}
        hasResponse
        onSelectAction={vi.fn()}
        summary={null}
        onOpenFullEditor={vi.fn()}
        onBackToWorkbench={vi.fn()}
      ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>

      const view = render(renderView(history))
      const scrollRegion = screen.getByRole('region', { name: '审核对话与历史处理轨迹' })
      expect(scrollRegion.scrollTop).toBe(320)

      const historyReadingPosition = conversationOffset - 8
      scrollRegion.scrollTop = historyReadingPosition
      fireEvent.scroll(scrollRegion)
      conversationOffset = 380
      view.rerender(renderView([
        ...history,
        { id: 'SYNTHETIC-HISTORY-2', tone: 'system', title: '归档校验中' },
      ]))
      expect(scrollRegion.scrollTop).toBe(historyReadingPosition)

      const conversationViewportOffset = 80
      scrollRegion.scrollTop = conversationOffset + conversationViewportOffset
      fireEvent.scroll(scrollRegion)
      conversationOffset = 440
      view.rerender(renderView([
        ...history,
        { id: 'SYNTHETIC-HISTORY-2', tone: 'system', title: '归档校验中' },
        { id: 'SYNTHETIC-HISTORY-3', tone: 'complete', title: '归档处理已完成' },
      ]))
      expect(scrollRegion.scrollTop).toBe(440 + conversationViewportOffset)
    } finally {
      boundingRect.mockRestore()
    }
  })
})
