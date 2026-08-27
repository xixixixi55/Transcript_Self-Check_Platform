import { fireEvent, render, screen } from '@testing-library/react'
import type { InspectionReport } from '@biji/shared/types'
import { describe, expect, it, vi } from 'vitest'
import type { GuidedReviewAction, GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'
import { GuidedReviewCard } from './GuidedReviewCard'
import { GuidedReviewHistory } from './GuidedReviewHistory'
import { GuidedReviewView } from './GuidedReviewView'

const history: GuidedReviewHistoryItem[] = [
  { id: 'SYNTHETIC-HISTORY-1', tone: 'complete', title: '报告内容已自动识别', detail: '已从合成报告整理文号。' },
]
const documentAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-DOCUMENT', kind: 'pending_item', title: '处理文号', description: '当前必填字段为空。',
  pendingItem: {
    id: 'SYNTHETIC-PENDING-DOCUMENT', sectionId: 'review-section-document',
    targetId: 'review-target-document-number', sectionLabel: '文书信息', fieldLabel: '文号',
    reason: '当前必填字段为空。', severity: 'warning', kind: 'required_missing',
  },
}
const waitingAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-WAITING', kind: 'waiting', title: '正在生成压缩分卷',
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
  it('keeps history before the current conversation and exposes global review controls', () => {
    const selectAction = vi.fn()
    const updateReport = vi.fn()
    render(<GuidedReviewView
      history={history}
      currentAction={documentAction}
      allActions={[documentAction, waitingAction]}
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
    expect(screen.getByText('报告内容已自动识别')).toBeTruthy()
    expect(screen.getByText('獬豸助手')).toBeTruthy()

    const pendingButton = screen.getByRole('button', { name: '查看全部待处理事项' })
    const summaryButton = screen.getByRole('button', { name: '查看已整理信息' })
    expect(pendingButton.getAttribute('aria-controls')).toBe('guided-review-pending-panel')
    expect(summaryButton.getAttribute('aria-controls')).toBe('guided-review-summary-panel')
    fireEvent.click(pendingButton)
    expect(screen.getByLabelText('全部待处理事项').id).toBe('guided-review-pending-panel')
    fireEvent.click(screen.getByRole('button', { name: /正在生成压缩分卷/ }))
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
      history={[]}
      currentAction={waitingAction}
      allActions={[waitingAction]}
      onSelectAction={vi.fn()}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    expect(screen.getByText('办理轨迹会随案件现有事实逐步形成。')).toBeTruthy()
    expect(screen.getByText('正在生成压缩分卷')).toBeTruthy()
    expect(screen.queryByText(/30%|问题\s*\d+\s*\/\s*\d+/)).toBeNull()
  })
})

describe('GuidedReviewHistory', () => {
  it('follows appended records only while the user remains at the end', () => {
    const view = render(<GuidedReviewHistory items={history} />)
    const region = screen.getByRole('region', { name: '历史处理轨迹' })
    Object.defineProperties(region, {
      scrollHeight: { configurable: true, value: 600 },
      clientHeight: { configurable: true, value: 200 },
    })
    region.scrollTop = 400
    fireEvent.scroll(region)
    view.rerender(<GuidedReviewHistory items={[...history, { id: 'SYNTHETIC-HISTORY-2', tone: 'system', title: '归档校验中' }]} />)
    expect(region.scrollTop).toBe(600)

    region.scrollTop = 120
    fireEvent.scroll(region)
    view.rerender(<GuidedReviewHistory items={[
      ...history,
      { id: 'SYNTHETIC-HISTORY-2', tone: 'system', title: '归档校验中' },
      { id: 'SYNTHETIC-HISTORY-3', tone: 'complete', title: '归档处理已完成' },
    ]} />)
    expect(region.scrollTop).toBe(120)

    region.scrollTop = 400
    fireEvent.scroll(region)
    view.rerender(<GuidedReviewHistory items={[
      ...history,
      { id: 'SYNTHETIC-HISTORY-2', tone: 'system', title: '归档校验中' },
      { id: 'SYNTHETIC-HISTORY-3', tone: 'complete', title: '归档处理已完成' },
      { id: 'SYNTHETIC-HISTORY-4', tone: 'complete', title: '介质编号已整理' },
    ]} />)
    expect(region.scrollTop).toBe(600)
  })
})
