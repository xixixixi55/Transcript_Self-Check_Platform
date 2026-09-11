import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { InspectionReport } from '@biji/shared/types'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { GuidedReviewAction, GuidedReviewHistoryField, GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'
import { GuidedReviewCard } from './GuidedReviewCard'
import { GuidedReviewView } from './GuidedReviewView'

const history: GuidedReviewHistoryItem[] = [
  {
    id: 'SYNTHETIC-HISTORY-1', tone: 'complete', title: '文书与委托信息',
    fields: [{
      label: '委托人员', value: 'SYNTHETIC-PERSON-A、SYNTHETIC-PERSON-B', userProvided: true, targetId: 'review-target-entrust-persons',
    }],
  },
  {
    id: 'SYNTHETIC-HISTORY-2', tone: 'complete', title: '检材与图片 · 1 项',
    materials: [{
      id: 'SYNTHETIC-MATERIAL-1', label: '检材 1 · SYN-JC00000001', photoCount: 2, requiredPhotoCount: 2,
      userProvided: true, sourceLabel: '人工添加', targetId: 'review-target-evidence-0', fields: [{
        label: '设备', value: 'SYNTHETIC PHONE', targetId: 'review-target-evidence-0',
      }, {
        label: 'IMEI 1', value: 'SYNTHETIC-IMEI-1', userProvided: true, sourceLabel: '已修改', targetId: 'review-target-evidence-0',
      }],
    }],
  },
  {
    id: 'SYNTHETIC-HISTORY-3', tone: 'complete', title: '检查结果',
    fields: [{
      label: '检查步骤 1', value: 'SYNTHETIC SYSTEM-GENERATED STEP', targetId: 'review-target-process-step-0',
    }],
  },
]
const documentAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-DOCUMENT', kind: 'pending_item', title: '请输入文号', description: '当前必填字段为空。',
  advanceOnEnter: true,
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
const completedPhotoField: GuidedReviewHistoryField = { label: '检材照片', value: '已上传 2 张图片', userProvided: true, targetId: 'review-target-material-photos' }

beforeEach(() => {
  window.localStorage.clear()
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: vi.fn(),
  })
})
const recoveryAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-RECOVERY', kind: 'save_recovery', title: '请恢复草稿保存',
  description: 'SYNTHETIC/TEST：保存链路需要恢复。',
}
const readyAction: GuidedReviewAction = {
  id: 'SYNTHETIC-ACTION-READY', kind: 'ready', title: '当前审核已完成',
  description: 'SYNTHETIC/TEST：请保存并退出；返回案件工作台后可完成导出。',
}
const deferredAction: GuidedReviewAction = {
  id: 'archive-deferred', kind: 'archive_deferred', title: '草稿已保存',
  description: '压缩已设为稍后处理。当前没有待填写事项，稍后可从案件工作台继续。',
}
const archiveDecisionAction: GuidedReviewAction = {
  id: 'archive-decision', kind: 'archive_decision', title: '请选择压缩时机',
  description: '可以现在开始压缩，也可以继续稍后处理。',
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
  it('keeps only quick batch supplementation after evidence is marked incomplete', () => {
    const onEvidenceCompletenessChange = vi.fn()
    const onOpenFullEditor = vi.fn()
    const updateReport = vi.fn()
    render(<GuidedReviewCard action={evidenceCompletenessAction} report={report} updateReport={updateReport}
      readOnly={false} onEvidenceCompletenessChange={onEvidenceCompletenessChange} />)

    const incompleteButton = screen.getByRole('button', { name: '检材信息不完整，手工添加检材' })
    expect(screen.queryByRole('button', { name: '确认检材信息完整' })).toBeNull()
    expect(incompleteButton.querySelector('.anticon-file-add')).toBeTruthy()
    expectCircularIconButton(incompleteButton)

    fireEvent.click(incompleteButton)
    expect(screen.getByRole('textbox', { name: '快捷批量添加检材' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '快捷批量补充检材' })).toBeNull()
    expect(screen.queryByRole('button', { name: /逐项编辑/ })).toBeNull()
    expect(onOpenFullEditor).not.toHaveBeenCalled()
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

    const input = screen.getByRole('textbox', { name: '快捷批量添加检材' })
    expect(input.getAttribute('aria-describedby')).toBe('quick-evidence-format-help')
    fireEvent.change(input, { target: { value: [
      '',
      'SYNTHETIC Pad平板一部（SYNTHETIC/TEST：屏幕损坏）SYN-JC00000003',
      'SYNTHETIC Phone 6手机一部（SYNTHETIC/TEST：损坏无法提取）SYN-JC00000001',
      'SYNTHETIC Phone 7手机一部（SYNTHETIC/TEST：无法开机）SYN-JC00000002',
    ].join('\n') } })
    fireEvent.click(screen.getByRole('button', { name: '解析、排序并预览' }))

    const parsedNotice = screen.getByText('已识别并排序 3 项检材，请确认后添加。')
    expect(parsedNotice.closest('.ant-message')).toBeTruthy()
    expect(document.querySelector('.guided-review-card__quick-evidence .ant-alert-success')).toBeNull()
    expect(screen.getByText(/SYNTHETIC Phone 6 · 手机/)).toBeTruthy()
    expect(screen.getByText(/SYNTHETIC Pad · 平板/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: '一键排序' })).toBeNull()
    expect(screen.getByRole('status').textContent).toBe('预览已按检材编号自然升序排列，确认添加时将同步排序全部检材。')
    expect(updateReport).not.toHaveBeenCalled()
    expect((input as HTMLTextAreaElement).value.split('\n').map(line => line.match(/SYN-JC\d+/)?.[0])).toEqual([
      'SYN-JC00000001', 'SYN-JC00000002', 'SYN-JC00000003',
    ])
    const confirmAddButton = screen.getByRole('button', { name: '确认添加 3 项检材' })
    expect(confirmAddButton.classList.contains('guided-review-card__quick-evidence-confirm')).toBe(true)
    expect(confirmAddButton.classList.contains('ant-btn-circle')).toBe(false)
    expect(confirmAddButton.textContent).toContain('确认添加 3 项检材')
    expect(confirmAddButton.querySelector('.anticon-file-add')).toBeTruthy()
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
    fireEvent.click(screen.getByRole('button', { name: '解析、排序并预览' }))
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.getByText(/第 1 行：格式不正确/)).toBeTruthy()
    expect(screen.getByText(/第 2 行：检材编号 SYN-JC00000000 已存在/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /确认添加/ })).toBeNull()
    expect((input as HTMLTextAreaElement).value).toContain('半角括号')

    fireEvent.change(input, { target: { value: [
      'SYNTHETIC Duplicate A手机一部（SYNTHETIC/TEST：重复编号）SYN-JC00000005',
      'SYNTHETIC Duplicate B平板一部（SYNTHETIC/TEST：重复编号）SYN-JC00000005',
    ].join('\n') } })
    fireEvent.click(screen.getByRole('button', { name: '解析、排序并预览' }))
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
    fireEvent.click(screen.getByRole('button', { name: '解析、排序并预览' }))
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
    fireEvent.click(screen.getByRole('button', { name: '解析、排序并预览' }))
    expect(updateReport).not.toHaveBeenCalled()
    expect(screen.getByText('当前检材编号无法安全排序，已保持原顺序。')).toBeTruthy()
  })

  it('shows Word preview on the left and conversation on the right without a pane switch', () => {
    const selectAction = vi.fn()
    const updateReport = vi.fn()
    const openFullEditor = vi.fn()
    const revisitHandledField = vi.fn()
    const scrollIntoView = vi.fn()
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    })
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      previouslyHandledFields={[{
        label: '检材完整性', value: '已确认', userProvided: true, targetId: 'review-target-evidence-completeness',
      }, completedPhotoField]}
      currentAction={documentAction}
      allActions={[documentAction, waitingAction]}
      hasResponse
      onSelectAction={selectAction}
      onRevisitHandledField={revisitHandledField}
      onBackToWorkbench={vi.fn()}
    >
      <GuidedReviewCard action={documentAction} report={report} updateReport={updateReport} readOnly={false} />
    </GuidedReviewView>)

    const historyRegion = screen.getByRole('region', { name: 'Word 内容预览' })
    const conversationRegion = screen.getByRole('region', { name: '当前对话' })
    expect(historyRegion.compareDocumentPosition(conversationRegion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByText('Word 内容预览在左，对话在右')).toBeNull()
    expect(screen.queryByText('按文书结构汇总，供快速核对')).toBeNull()
    expect(screen.queryByRole('button', { name: '交换 Word 内容预览与对话的位置' })).toBeNull()
    expect(screen.getByText('文书与委托信息')).toBeTruthy()
    expect(screen.getByText('委托人员：')).toBeTruthy()
    expect(screen.getByText('SYNTHETIC-PERSON-A、SYNTHETIC-PERSON-B')).toBeTruthy()
    expect(screen.getAllByText('用户填写')).toHaveLength(1)
    expect(screen.getByText('人工添加')).toBeTruthy()
    expect(screen.getByText('已修改')).toBeTruthy()
    expect(screen.getByText('检材 1 · SYN-JC00000001')).toBeTruthy()
    expect(screen.getByText('2/2').getAttribute('aria-label'))
      .toBe('检材 1 · SYN-JC00000001：已上传 2 张图片，共需 2 张')
    expect(screen.getByText('獬豸助手')).toBeTruthy()
    expect(screen.getByText('1 项待处理')).toBeTruthy()
    const assistantMessage = screen.getByRole('status', { name: '獬豸助手提示' })
    expect(assistantMessage.textContent).toContain('请输入文号')
    expect(assistantMessage.textContent).not.toContain('当前必填字段为空。')
    expect(assistantMessage.querySelector('.guided-review-card__description')).toBeNull()
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

    const pendingButton = screen.getByRole('button', { name: '查看已填内容与待办（1 项待处理）' })
    expect(pendingButton.querySelector('.anticon-unordered-list')).toBeTruthy()
    expectCircularIconButton(pendingButton)
    expect(screen.queryByRole('button', { name: '查看已整理信息' })).toBeNull()
    expect(screen.queryByRole('button', { name: '完整审核编辑' })).toBeNull()
    expect(screen.getByRole('button', { name: '返回案件工作台' }).querySelector('.anticon-home')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '更多操作' })).toBeNull()
    expect(pendingButton.getAttribute('aria-controls')).toBe('guided-review-pending-panel')
    fireEvent.click(pendingButton)
    const pendingPanel = screen.getByLabelText('已填内容与待办')
    expect(pendingPanel.id).toBe('guided-review-pending-panel')
    expect(document.activeElement).toBe(pendingPanel)
    expect(scrollIntoView).toHaveBeenLastCalledWith({ block: 'nearest', inline: 'nearest' })
    expect(pendingPanel.textContent).not.toContain(documentAction.description)
    expect(pendingPanel.textContent).not.toContain(waitingAction.description)
    expect(pendingPanel.textContent).not.toContain('进入完整审核编辑')
    expect(screen.getByRole('button', { name: /请输入文号.*当前/ }).getAttribute('aria-current')).toBe('true')
    expect(screen.getByRole('button', { name: /请稍候，正在生成压缩分卷.*后台中/ })).toBeTruthy()
    expect(within(pendingPanel).getByRole('heading', { name: '已填内容' })).toBeTruthy()
    expect(within(pendingPanel).getByText('委托人员')).toBeTruthy()
    expect(within(pendingPanel).getByText('SYNTHETIC-PERSON-A、SYNTHETIC-PERSON-B')).toBeTruthy()
    expect(within(pendingPanel).getByText('检材完整性')).toBeTruthy()
    expect(within(pendingPanel).getByText('已确认')).toBeTruthy()
    expect(within(pendingPanel).queryByText('检材 1 · SYN-JC00000001 · IMEI 1')).toBeNull()
    expect(within(pendingPanel).queryByText('SYNTHETIC-IMEI-1')).toBeNull()
    expect(within(pendingPanel).getAllByText('已上传 2 张图片')).toHaveLength(1)
    expect(within(pendingPanel).getByText('检查步骤 1')).toBeTruthy()
    expect(within(pendingPanel).getByText('SYNTHETIC SYSTEM-GENERATED STEP')).toBeTruthy()
    fireEvent.click(within(pendingPanel).getByRole('button', { name: '修改检材照片' }))
    expect(revisitHandledField).toHaveBeenCalledWith(completedPhotoField)
    expect(openFullEditor).not.toHaveBeenCalled()
    fireEvent.click(pendingButton)
    expect(screen.queryByRole('button', { name: '修改其他已填内容' })).toBeNull()
    expect(screen.queryByRole('heading', { name: '其他内容' })).toBeNull()
    expect(openFullEditor).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /请稍候，正在生成压缩分卷/ }))
    expect(selectAction).toHaveBeenCalledWith(waitingAction.id)

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
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    expect(screen.getByText('暂无可预览内容')).toBeTruthy()
    expect(screen.getByText('请先完善笔录信息，内容会在这里同步更新。')).toBeTruthy()
    expect(screen.getByText('请稍候，正在生成压缩分卷')).toBeTruthy()
    expect(screen.getByText('后台处理中')).toBeTruthy()
    expect(document.querySelector('[data-mood="verifying"]')).toBeTruthy()
    expect(screen.getAllByText('后台任务仍在运行，可继续处理其他待办。')).toHaveLength(1)
    expect(screen.queryByRole('group', { name: '请选择操作' })).toBeNull()
    expect(screen.queryByRole('group', { name: '你的回复' })).toBeNull()
    expect(screen.queryByText(/30%|问题\s*\d+\s*\/\s*\d+/)).toBeNull()
  })

  it('omits empty assistant copy without hiding useful guidance', () => {
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[documentAction]}
      hasResponse
      assistantMessage={{ title: '介质编号（可提前填写）' }}
      onSelectAction={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    const prefillMessage = screen.getByRole('status', { name: '獬豸助手提示' })
    expect(prefillMessage.textContent).toBe('介质编号（可提前填写）')
    expect(prefillMessage.querySelector('.guided-review-card__description')).toBeNull()

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={photoAction}
      allActions={[photoAction]}
      hasResponse
      onSelectAction={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={photoAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    const photoMessage = screen.getByRole('status', { name: '獬豸助手提示' })
    expect(photoMessage.textContent).toContain('还需上传 2 张图片（每个检材需 2 张）。')
    expect(photoMessage.querySelector('.guided-review-card__description')).toBeTruthy()
  })

  it('uses serious and celebratory mascot states for recovery and ready actions', () => {
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={recoveryAction}
      allActions={[recoveryAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
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
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={readyAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)
    expect(view.container.querySelector('[data-mood="complete"]')).toBeTruthy()
  })

  it('presents deferred archiving as a terminal outcome with explicit prioritized actions', () => {
    const backToWorkbench = vi.fn()
    const startArchiveNow = vi.fn()
    const returnToPreviousAction = vi.fn()
    render(<GuidedReviewView
      conversationKey="SYNTHETIC-DEFERRED-CASE"
      history={history}
      currentAction={deferredAction}
      allActions={[deferredAction, archiveDecisionAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      canReturnToPrevious
      onReturnToPreviousAction={returnToPreviousAction}
      onStartArchiveNow={startArchiveNow}
      onBackToWorkbench={backToWorkbench}
    ><GuidedReviewCard action={deferredAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    const terminalActions = screen.getByRole('group', { name: '稍后处理完成后的操作' })
    const backButton = within(terminalActions).getByRole('button', { name: '返回案件工作台' })
    const archiveButton = within(terminalActions).getByRole('button', { name: '现在压缩' })
    const reviseButton = within(terminalActions).getByRole('button', { name: '返回上一步修改' })
    expect(backButton.classList.contains('ant-btn-primary')).toBe(true)
    expect(backButton.compareDocumentPosition(archiveButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(archiveButton.compareDocumentPosition(reviseButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByRole('button', { name: '返回上一步' })).toBeNull()
    expect(screen.queryByRole('button', { name: /查看已填内容与待办/ })).toBeNull()

    fireEvent.click(backButton)
    fireEvent.click(archiveButton)
    fireEvent.click(reviseButton)
    expect(backToWorkbench).toHaveBeenCalledTimes(1)
    expect(startArchiveNow).toHaveBeenCalledTimes(1)
    expect(returnToPreviousAction).toHaveBeenCalledTimes(1)
  })

  it('hides the edit center after completion and keeps previous-next navigation', async () => {
    const returnToPreviousAction = vi.fn()
    const returnToCurrentAction = vi.fn()
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[documentAction, waitingAction]}
      hasResponse
      onSelectAction={vi.fn()}
      canReturnToPrevious
      onReturnToPreviousAction={returnToPreviousAction}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    const initialStepNavigation = screen.getByRole('button', { name: '返回上一步' })
    expect(initialStepNavigation.querySelector('.anticon-arrow-left')).toBeTruthy()
    expectCircularIconButton(initialStepNavigation, true)
    const initialReplyGroup = screen.getByRole('group', { name: '你的回复' })
    expect(initialReplyGroup.contains(initialStepNavigation)).toBe(true)
    const confirmationButton = screen.getByRole('button', { name: '进入下一步' })
    expect(confirmationButton.textContent).toBe('')
    expect(initialReplyGroup.contains(confirmationButton)).toBe(true)
    expect(initialStepNavigation.compareDocumentPosition(confirmationButton)
      & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByRole('button', { name: /查看已填内容与待办/ })).toBeTruthy()

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={waitingAction}
      allActions={[waitingAction]}
      hasResponse={false}
      onSelectAction={vi.fn()}
      canReturnToPrevious
      onReturnToPreviousAction={returnToPreviousAction}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    await waitFor(() => expect(screen.queryByLabelText('上一轮办理结果')).toBeNull())
    expect(screen.queryByText('文号已填写')).toBeNull()
    expect(document.querySelector('[data-mood="complete"]')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /查看已填内容与待办/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '返回上一步' }))
    expect(returnToPreviousAction).toHaveBeenCalledTimes(1)

    view.rerender(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[waitingAction]}
      hasResponse
      onSelectAction={vi.fn()}
      canReturnToPrevious
      canReturnToNext
      onReturnToPreviousAction={returnToPreviousAction}
      onReturnToNextAction={returnToCurrentAction}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)
    const returnToCurrentStep = screen.getByRole('button', { name: '进入下一步' })
    expect(returnToCurrentStep.querySelector('.anticon-arrow-right')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: '进入下一步' })).toHaveLength(1)
    expect(returnToCurrentStep.textContent).toBe('')
    expect(screen.getByRole('group', { name: '你的回复' }).contains(returnToCurrentStep)).toBe(true)
    fireEvent.click(returnToCurrentStep)
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
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={waitingAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)
    await waitFor(() => expect(screen.queryByLabelText('上一轮办理结果')).toBeNull())
  })

  it('keeps completed session actions in the edit center only while manual work remains', async () => {
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
      onSelectAction: vi.fn(), onRevisitAction: vi.fn(), onBackToWorkbench: vi.fn(),
    }
    const child = (action: GuidedReviewAction) => (
      <GuidedReviewCard action={action} report={report} updateReport={vi.fn()} readOnly={false} />
    )
    const view = render(<GuidedReviewView {...props} currentAction={actions[0]}
      allActions={[...actions, waitingAction]}>{child(actions[0])}</GuidedReviewView>)

    view.rerender(<GuidedReviewView {...props} currentAction={actions[1]}
      allActions={[...actions.slice(1), waitingAction]}>{child(actions[1])}</GuidedReviewView>)
    await waitFor(() => expect(document.querySelector('[data-mood="complete"]')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: /查看已填内容与待办/ }))
    expect(screen.getByRole('button', { name: '修改甲' })).toBeTruthy()

    view.rerender(<GuidedReviewView {...props} currentAction={waitingAction}
      allActions={[waitingAction]} hasResponse={false}>{child(waitingAction)}</GuidedReviewView>)
    expect(screen.queryByRole('button', { name: /查看已填内容与待办/ })).toBeNull()
    expect(screen.queryByRole('region', { name: '已填内容与待办' })).toBeNull()
  })

  it('acknowledges a manual action switch and stages the next response as a conversational turn', async () => {
    const view = render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[documentAction, photoAction]}
      hasResponse
      onSelectAction={vi.fn()}
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

  it('keeps the fixed pane order when a legacy preference requests conversation first', () => {
    window.localStorage.setItem('biji.guidedReview.splitOrder', 'conversation-first')
    render(<GuidedReviewView
      conversationKey="SYNTHETIC-CASE"
      history={history}
      currentAction={documentAction}
      allActions={[documentAction]}
      hasResponse
      onSelectAction={vi.fn()}
      onBackToWorkbench={vi.fn()}
    ><GuidedReviewCard action={documentAction} report={report} updateReport={vi.fn()} readOnly={false} /></GuidedReviewView>)

    const historyRegion = screen.getByRole('region', { name: 'Word 内容预览' })
    const conversationRegion = screen.getByRole('region', { name: '当前对话' })
    expect(historyRegion.compareDocumentPosition(conversationRegion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByRole('group', { name: '獬豸助手分栏' }).className)
      .toBe('guided-review-scroll')
    expect(screen.queryByRole('button', { name: '交换 Word 内容预览与对话的位置' })).toBeNull()
  })
})
