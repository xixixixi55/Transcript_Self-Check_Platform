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
const recoveryAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-RECOVERY', kind: 'save_recovery', title: '请恢复草稿保存',
  description: 'SYNTHETIC/TEST：保存链路需要恢复。',
}
const readyAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-READY', kind: 'ready', title: '请确认并生成笔录',
  description: 'SYNTHETIC/TEST：所需事项已经齐备。',
}
const evidenceCompletenessAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-EVIDENCE-COMPLETENESS', kind: 'pending_item', title: '请确认检材完整性',
  description: '请确认检材是否完整。',
  pendingItem: {
    id: 'SYNTHETIC-PENDING-EVIDENCE-COMPLETENESS', sectionId: 'review-section-introduction',
    targetId: 'review-target-evidence-completeness', sectionLabel: '一、绪论', fieldLabel: '检材完整性',
    reason: '请确认检材是否完整。', severity: 'warning', kind: 'confirmation_required',
  },
}

const photoAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-PHOTOS', kind: 'pending_item', title: '请上传检材照片',
  description: '还需上传 2 张图片（每个检材需 2 张）。',
  pendingItem: {
    id: 'SYNTHETIC-PENDING-PHOTOS', sectionId: 'review-section-attachments',
    targetId: 'review-target-material-photos', sectionLabel: '附件', fieldLabel: '检材照片',
    reason: '还需上传 2 张图片（每个检材需 2 张）。', severity: 'warning', kind: 'required_missing',
  },
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

function expectCircularIconButton(button: HTMLElement, primary = false) {
  expect(button.classList.contains('ant-btn-circle')).toBe(true)
  expect(button.textContent).toBe('')
  if (primary) expect(button.classList.contains('ant-btn-primary')).toBe(true)
}

describe('GuidedReviewView', () => {
  it('uses icon actions for complete evidence and manual evidence supplementation', () => {
    const onEvidenceCompletenessChange = vi.fn()
    const onOpenFullEditor = vi.fn()
    const updateReport = vi.fn()
    render(<GuidedReviewCard action={evidenceCompletenessAction} report={report} updateReport={updateReport}
      readOnly={false} onEvidenceCompletenessChange={onEvidenceCompletenessChange}
      onOpenFullEditor={onOpenFullEditor} />)

    const completeButton = screen.getByRole('button', { name: '确认检材信息完整' })
    const incompleteButton = screen.getByRole('button', { name: '检材信息不完整，手工添加检材' })
    expect(completeButton.querySelector('.anticon-check-circle')).toBeTruthy()
    expect(incompleteButton.querySelector('.anticon-file-add')).toBeTruthy()
    expectCircularIconButton(completeButton, true)
    expectCircularIconButton(incompleteButton)

    fireEvent.click(completeButton)
    expect(onEvidenceCompletenessChange).toHaveBeenCalledWith(true)
    fireEvent.click(incompleteButton)
    const batchModeButton = screen.getByRole('button', { name: '快捷批量补充检材' })
    const manualModeButton = screen.getByRole('button', { name: '逐项编辑检材' })
    expectCircularIconButton(batchModeButton, true)
    expectCircularIconButton(manualModeButton)
    expect(screen.queryByRole('textbox', { name: '快捷批量添加检材' })).toBeNull()
    fireEvent.click(manualModeButton)
    const addEvidenceButton = screen.getByRole('button', { name: '添加检材' })
    expectCircularIconButton(addEvidenceButton)
    const confirmCompleteButton = screen.getByRole('button', { name: '完成检材补充并确认完整' })
    expect(confirmCompleteButton.querySelector('.anticon-check-circle')).toBeTruthy()
    expectCircularIconButton(confirmCompleteButton, true)
    expect(screen.queryByRole('button', { name: '解析并预览' })).toBeNull()
    const switchToBatchButton = screen.getByRole('button', { name: '改用快捷批量补充' })
    expectCircularIconButton(switchToBatchButton)
    expect(onOpenFullEditor).not.toHaveBeenCalled()

    fireEvent.click(addEvidenceButton)
    expect(updateReport).toHaveBeenCalledWith('introduction.evidence_list', [
      expect.objectContaining({ evidence_number: '' }),
    ])
    expect(onEvidenceCompletenessChange).toHaveBeenLastCalledWith(false)
  })

  it('previews and appends newline-delimited unavailable evidence without accepting invalid batches', () => {
    const updateReport = vi.fn()
    const reportWithExistingEvidence: InspectionReport = {
      ...report,
      introduction: {
        ...report.introduction,
        evidence_list: [{
          id: 'SYNTHETIC-EXISTING', evidence_id: 'SYNTHETIC-EXISTING', device_type: '',
          device_name: 'SYNTHETIC Existing', material_type: 'phone',
          material_type_status: 'confirmed_by_user', material_type_source: 'user', extractable: false,
          unextractable_reason: 'SYNTHETIC/TEST：无法提取', evidence_number: 'SYN-JC00000000',
        }],
      },
    }
    render(<GuidedReviewCard action={evidenceCompletenessAction} report={reportWithExistingEvidence}
      updateReport={updateReport} readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '检材信息不完整，手工添加检材' }))
    fireEvent.click(screen.getByRole('button', { name: '快捷批量补充检材' }))
    expect(screen.getByText(/每行一项/)).toBeTruthy()
    expect(screen.getByText(/全角括号/)).toBeTruthy()

    const input = screen.getByRole('textbox', { name: '快捷批量添加检材' })
    expect(input.getAttribute('aria-describedby')).toBe('quick-evidence-format-help')
    fireEvent.change(input, { target: { value: [
      '',
      'SYNTHETIC Pad平板一部（SYNTHETIC/TEST：屏幕损坏）SYN-JC00000003',
      'SYNTHETIC Phone 6手机一部（SYNTHETIC/TEST：损坏无法提取）SYN-JC00000001',
      'SYNTHETIC Phone 7手机一部（SYNTHETIC/TEST：无法开机）SYN-JC00000002',
    ].join('\n') } })
    fireEvent.click(screen.getByRole('button', { name: '解析并预览' }))

    const parsedNotice = screen.getByText('已识别 3 项检材，请确认后添加。')
    expect(parsedNotice.closest('.ant-message')).toBeTruthy()
    expect(document.querySelector('.guided-review-card__quick-evidence .ant-alert-success')).toBeNull()
    expect(screen.getByText(/SYNTHETIC Phone 6 · 手机/)).toBeTruthy()
    expect(screen.getByText(/SYNTHETIC Pad · 平板/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '一键排序' }))
    expect(screen.getByText('已按检材编号自然升序排列。')).toBeTruthy()
    expect((input as HTMLTextAreaElement).value.split('\n').map(line => line.match(/SYN-JC\d+/)?.[0])).toEqual([
      'SYN-JC00000001', 'SYN-JC00000002', 'SYN-JC00000003',
    ])
    const confirmAddButton = screen.getByRole('button', { name: '确认添加 3 项检材' })
    expect(confirmAddButton.classList.contains('guided-review-card__quick-evidence-confirm')).toBe(true)
    expectCircularIconButton(confirmAddButton, true)
    expect(confirmAddButton.querySelector('.anticon-check-circle')).toBeTruthy()
    fireEvent.click(confirmAddButton)
    expect(updateReport).toHaveBeenCalledWith('introduction.evidence_list', [
      reportWithExistingEvidence.introduction.evidence_list[0],
      expect.objectContaining({
        device_name: 'SYNTHETIC Phone 6', material_type: 'phone', extractable: false,
        unextractable_reason: 'SYNTHETIC/TEST：损坏无法提取', evidence_number: 'SYN-JC00000001',
      }),
      expect.objectContaining({ evidence_number: 'SYN-JC00000002' }),
      expect.objectContaining({ material_type: 'tablet', evidence_number: 'SYN-JC00000003' }),
    ])

    fireEvent.change(input, { target: { value: [
      'SYNTHETIC Invalid手机一部(SYNTHETIC/TEST：半角括号)SYN-JC00000004',
      'SYNTHETIC Duplicate手机一部（SYNTHETIC/TEST：重复编号）SYN-JC00000000',
    ].join('\n') } })
    fireEvent.click(screen.getByRole('button', { name: '解析并预览' }))
    expect(screen.getByText(/第 1 行：格式不正确/)).toBeTruthy()
    expect(screen.getByText(/第 2 行：检材编号 SYN-JC00000000 已存在/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /确认添加/ })).toBeNull()
    expect((input as HTMLTextAreaElement).value).toContain('半角括号')

    fireEvent.change(input, { target: { value: [
      'SYNTHETIC Duplicate A手机一部（SYNTHETIC/TEST：重复编号）SYN-JC00000005',
      'SYNTHETIC Duplicate B平板一部（SYNTHETIC/TEST：重复编号）SYN-JC00000005',
    ].join('\n') } })
    fireEvent.click(screen.getByRole('button', { name: '解析并预览' }))
    expect(screen.getByText(/第 2 行：检材编号 SYN-JC00000005 在本次输入中重复/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /确认添加/ })).toBeNull()
  })

  it('sorts existing evidence by the report-recognition natural number rule only on explicit request', () => {
    const updateReport = vi.fn()
    const evidence = ['SYN-JC10', 'SYN-JC2', 'SYN-JC1'].map(evidenceNumber => ({
      id: `SYNTHETIC-${evidenceNumber}`, evidence_id: `SYNTHETIC-${evidenceNumber}`,
      device_type: '', device_name: evidenceNumber, evidence_number: evidenceNumber,
    }))
    render(<GuidedReviewCard action={evidenceCompletenessAction} report={{
      ...report, introduction: { ...report.introduction, evidence_list: evidence },
    }} updateReport={updateReport} readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '检材信息不完整，手工添加检材' }))
    fireEvent.click(screen.getByRole('button', { name: '快捷批量补充检材' }))
    fireEvent.click(screen.getByRole('button', { name: '一键排序' }))
    expect(updateReport).toHaveBeenCalledWith('introduction.evidence_list', [evidence[2], evidence[1], evidence[0]])
    expect(screen.getByText('已按检材编号自然升序排列。')).toBeTruthy()
  })

  it('keeps the existing order when evidence numbers cannot be safely sorted', () => {
    const updateReport = vi.fn()
    const evidence = ['SYNTHETIC-UNKNOWN', 'SYN-JC2'].map(evidenceNumber => ({
      id: `SYNTHETIC-${evidenceNumber}`, evidence_id: `SYNTHETIC-${evidenceNumber}`,
      device_type: '', device_name: evidenceNumber, evidence_number: evidenceNumber,
    }))
    render(<GuidedReviewCard action={evidenceCompletenessAction} report={{
      ...report, introduction: { ...report.introduction, evidence_list: evidence },
    }} updateReport={updateReport} readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '检材信息不完整，手工添加检材' }))
    fireEvent.click(screen.getByRole('button', { name: '快捷批量补充检材' }))
    fireEvent.click(screen.getByRole('button', { name: '一键排序' }))
    expect(updateReport).not.toHaveBeenCalled()
    expect(screen.getByText('当前检材编号无法安全排序，已保持原顺序。')).toBeTruthy()
  })

  it('keeps full history above the current conversation while exposing global review controls', () => {
    const selectAction = vi.fn()
    const updateReport = vi.fn()
    const scrollIntoView = vi.fn()
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    })
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
    expect(screen.queryByText('其他操作')).toBeNull()
    const mascot = view.container.querySelector<HTMLImageElement>('.guided-review-conversation__mascot img')
    const conversationBody = view.container.querySelector('.guided-review-conversation__body')
    const conversationContent = view.container.querySelector('.guided-review-conversation__content')
    const conversationUtilities = view.container.querySelector('.guided-review-conversation__utilities')
    expect(conversationBody?.querySelector(':scope > .guided-review-conversation__mascot img')).toBe(mascot)
    expect(conversationBody?.querySelector(':scope > .guided-review-conversation__content')).toBe(conversationContent)
    expect(conversationContent?.contains(mascot)).toBe(false)
    expect(conversationBody?.contains(conversationUtilities)).toBe(false)
    expect(mascot?.getAttribute('src')).toContain('xiezhi-assistant-states.png')
    expect(mascot?.closest('[data-mood]')?.getAttribute('data-mood')).toBe('listening')
    fireEvent.error(mascot!)
    expect(view.container.querySelector('.anticon-safety-certificate')).toBeTruthy()

    const pendingButton = screen.getByRole('button', { name: '查看全部当前事项（2）' })
    const summaryButton = screen.getByRole('button', { name: '查看已整理信息' })
    expect(pendingButton.querySelector('.anticon-unordered-list')).toBeTruthy()
    expect(summaryButton.querySelector('.anticon-file-done')).toBeTruthy()
    expectCircularIconButton(pendingButton)
    expectCircularIconButton(summaryButton)
    const fullEditorButton = screen.getByRole('button', { name: '完整审核编辑' })
    expect(fullEditorButton.querySelector('.anticon-edit')).toBeTruthy()
    expect(fullEditorButton.classList.contains('ant-btn-primary')).toBe(true)
    expect(fullEditorButton.classList.contains('guided-review-tools__primary')).toBe(true)
    expect(screen.getByRole('button', { name: '返回案件工作台' }).querySelector('.anticon-home')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '更多操作' })).toBeNull()
    expect(pendingButton.getAttribute('aria-controls')).toBe('guided-review-pending-panel')
    expect(summaryButton.getAttribute('aria-controls')).toBe('guided-review-summary-panel')
    fireEvent.click(pendingButton)
    const pendingPanel = screen.getByLabelText('全部当前事项')
    expect(pendingPanel.id).toBe('guided-review-pending-panel')
    expect(document.activeElement).toBe(pendingPanel)
    expect(scrollIntoView).toHaveBeenLastCalledWith({ block: 'nearest', inline: 'nearest' })
    expect(screen.getByRole('button', { name: /请输入文号.*当前/ }).getAttribute('aria-current')).toBe('true')
    expect(screen.getByRole('button', { name: /请稍候，正在生成压缩分卷.*后台中/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /请稍候，正在生成压缩分卷/ }))
    expect(selectAction).toHaveBeenCalledWith(waitingAction.id)

    fireEvent.click(summaryButton)
    const summaryPanel = screen.getByLabelText('已整理信息')
    expect(summaryPanel.id).toBe('guided-review-summary-panel')
    expect(document.activeElement).toBe(summaryPanel)
    expect(scrollIntoView).toHaveBeenCalledTimes(2)
    expect(screen.getByText('SYNTHETIC ORGANIZED SUMMARY')).toBeTruthy()
    expect(updateReport).not.toHaveBeenCalled()

    fireEvent.change(screen.getByRole('textbox', { name: '文号' }), { target: { value: 'SYN-TEST〔2026〕009号' } })
    expect(updateReport).toHaveBeenCalledWith('document_number', 'SYN-TEST〔2026〕009号')
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: originalScrollIntoView,
    })
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
    expect(document.querySelector('[data-mood="verifying"]')).toBeTruthy()
    expect(screen.getAllByText('后台任务仍在运行，可继续处理其他待办。')).toHaveLength(1)
    expect(screen.queryByText(/30%|问题\s*\d+\s*\/\s*\d+/)).toBeNull()
  })

  it('uses serious and celebratory mascot states for recovery and ready actions', () => {
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={recoveryAction}
      allActions={[recoveryAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={recoveryAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    expect(view.container.querySelector('[data-mood="warning"]')).toBeTruthy()
    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={readyAction}
      allActions={[readyAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={readyAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)
    expect(view.container.querySelector('[data-mood="complete"]')).toBeTruthy()
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
    const revisitAction = vi.fn()
    const returnToPreviousAction = vi.fn()
    const returnToCurrentAction = vi.fn()
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[documentAction, waitingAction]}
      hasResponse
      onSelectAction={vi.fn()}
      onRevisitAction={revisitAction}
      canReturnToPrevious
      onReturnToPreviousAction={returnToPreviousAction}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    const initialStepNavigation = screen.getByRole('button', { name: '返回上一步' })
    expectCircularIconButton(initialStepNavigation)
    const initialReplyGroup = screen.getByRole('group', { name: '你的回复' })
    expect(initialStepNavigation.compareDocumentPosition(initialReplyGroup)
      & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={waitingAction}
      allActions={[waitingAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      onRevisitAction={revisitAction}
      canReturnToPrevious
      onReturnToPreviousAction={returnToPreviousAction}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    await waitFor(() => expect(screen.getByLabelText('上一轮办理结果')).toBeTruthy())
    expect(screen.getByText('文号已填写')).toBeTruthy()
    expect(screen.getByText('文号已经纳入当前笔录。后台任务还在继续，我会同步核对结果。')).toBeTruthy()
    expect(document.querySelector('[data-mood="complete"]')).toBeTruthy()
    const revisitButton = screen.getByRole('button', { name: '修改文号' })
    expectCircularIconButton(revisitButton)
    fireEvent.click(revisitButton)
    expect(revisitAction).toHaveBeenCalledWith(documentAction)
    expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent).toContain('请稍候，正在生成压缩分卷')
    fireEvent.click(screen.getByRole('button', { name: '返回上一步' }))
    expect(returnToPreviousAction).toHaveBeenCalledTimes(1)

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[waitingAction]}
      hasResponse
      onSelectAction={vi.fn()}
      onRevisitAction={revisitAction}
      canReturnToPrevious
      isReviewingPrevious
      onReturnToPreviousAction={returnToPreviousAction}
      onReturnToCurrentAction={returnToCurrentAction}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)
    fireEvent.click(screen.getByRole('button', { name: '返回当前步骤' }))
    expect(returnToCurrentAction).toHaveBeenCalledTimes(1)

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-OTHER-CASE"
      history={history}
      currentAction={waitingAction}
      allActions={[waitingAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      canReturnToPrevious={false}
      onReturnToPreviousAction={returnToPreviousAction}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)
    await waitFor(() => expect(screen.queryByLabelText('上一轮办理结果')).toBeNull())
  })

  it('keeps the latest three completed turns and summarizes older session turns', async () => {
    const actions = ['甲', '乙', '丙', '丁'].map((fieldLabel, index): GuidedReviewAction => ({
      ...documentAction,
      id: `SYNTHETIC-ACTION-${fieldLabel}`,
      title: `请填写${fieldLabel}`,
      pendingItem: {
        ...documentAction.pendingItem!,
        id: `SYNTHETIC-PENDING-${fieldLabel}`,
        fieldLabel,
      },
    }))
    const props = {
      conversationKey: 'SYNTHETIC-CASE', history, hasResponse: true,
      onSelectAction: vi.fn(), onRevisitAction: vi.fn(), summary: null,
      onOpenFullEditor: vi.fn(), onBackToWorkbench: vi.fn(),
    }
    const child = (action: GuidedReviewAction) => (
      <GuidedReviewCard action={action} report={report} updateReport={vi.fn()} readOnly={false} />
    )
    const view = render(<GuidedReviewView {...props} currentAction={actions[0]}
      allActions={[...actions, waitingAction]}>{child(actions[0])}</GuidedReviewView>)

    for (let index = 1; index < actions.length; index += 1) {
      const action = actions[index]
      view.rerender(<GuidedReviewView {...props} currentAction={action}
        allActions={[...actions.slice(index), waitingAction]}>{child(action)}</GuidedReviewView>)
      await waitFor(() => expect(screen.getByRole('button', { name: `修改${actions[index - 1].pendingItem?.fieldLabel}` })).toBeTruthy())
    }
    view.rerender(<GuidedReviewView {...props} currentAction={waitingAction}
      allActions={[waitingAction]} hasResponse={false}>{child(waitingAction)}</GuidedReviewView>)

    await waitFor(() => expect(screen.getByText('更早已完成 1 项')).toBeTruthy())
    expect(screen.queryByRole('button', { name: '修改甲' })).toBeNull()
    expect(screen.getByRole('button', { name: '修改乙' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '修改丙' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '修改丁' })).toBeTruthy()
  })

  it('acknowledges a manual action switch and stages the next response as a conversational turn', async () => {
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[documentAction, photoAction]}
      hasResponse
      onSelectAction={vi.fn()}
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)
    const initialMascotFigure = view.container.querySelector('.guided-review-conversation__mascot-figure')

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={photoAction}
      allActions={[documentAction, photoAction]}
      hasResponse
      onSelectAction={vi.fn()}
      canReturnToPrevious
      summary={null}
      onOpenFullEditor={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={photoAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    await waitFor(() => expect(screen.getByLabelText('事项切换说明')).toBeTruthy())
    expect(screen.getByLabelText('事项切换说明').textContent)
      .toContain('好的，先处理“检材照片”。“文号”仍保留在待办中，之后可以继续。')
    expect(screen.queryByLabelText('上一轮办理结果')).toBeNull()
    expect(screen.getByRole('group', { name: '你的回复' }).getAttribute('data-action-id'))
      .toBe(photoAction.id)
    const nextMascotFigure = view.container.querySelector('.guided-review-conversation__mascot-figure')
    expect(nextMascotFigure?.getAttribute('data-action-id')).toBe(photoAction.id)
    expect(nextMascotFigure).not.toBe(initialMascotFigure)
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
