import { fireEvent, render, screen } from '@testing-library/react'
import type { InspectionReport } from '@biji/shared/types'
import { describe, expect, it, vi } from 'vitest'
import type { GuidedReviewAction } from '../hooks/useGuidedReviewCards'
import { GuidedReviewCard } from './GuidedReviewCard'
import { GuidedReviewView } from './GuidedReviewView'

const action: GuidedReviewAction = {
  id: 'SYNTHETIC-DOCUMENT', kind: 'pending_item', title: '请输入文号',
  description: '当前必填字段为空。', advanceOnEnter: true,
  pendingItem: {
    id: 'SYNTHETIC-DOCUMENT', sectionId: 'review-section-document',
    targetId: 'review-target-document-number', sectionLabel: '文书信息', fieldLabel: '文号',
    reason: '当前必填字段为空。', severity: 'warning', kind: 'required_missing',
  },
}

const report = {
  title: 'SYNTHETIC/TEST RECORD', document_number: '',
  introduction: {
    entrust_unit: '', entrust_persons: [], entrust_time: '', case_summary: '', evidence_list: [],
    inspection_requirement: '', inspection_time_range: '', inspectors: [], inspection_place: '',
  },
  inspection: {
    method: '', hardware_device: '', software_tools: [], process_steps: [],
    result: {
      evidence_number: '', software_name: '', software_version: '', data_summary: '',
      rar_filename: '', md5_hash: '', file_size: '',
    },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
} as InspectionReport

function confirmationView(confirm: () => void, disabled = false) {
  return <GuidedReviewView conversationKey="SYNTHETIC-CASE" history={[]}
    currentAction={action} allActions={[action]} hasResponse onSelectAction={vi.fn()}
    onConfirmCurrentAction={confirm} confirmCurrentActionDisabled={disabled}
    onOpenFullEditor={vi.fn()} onBackToWorkbench={vi.fn()}>
    <GuidedReviewCard action={action} report={report} updateReport={vi.fn()} readOnly={disabled} />
  </GuidedReviewView>
}

describe('GuidedReviewView text confirmation', () => {
  it('uses the same completion callback for the action button and an unmodified Enter', () => {
    const confirm = vi.fn()
    render(confirmationView(confirm))

    const input = screen.getByRole('textbox', { name: '文号' })
    const enterKey = screen.getByRole('button', { name: '确认并进入下一步' })
      .querySelector('svg[data-direction="right"]')
    expect(enterKey).toBeInstanceOf(SVGElement)
    fireEvent.click(screen.getByRole('button', { name: '确认并进入下一步' }))
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(confirm).toHaveBeenCalledTimes(1)

    fireEvent.keyDown(input, { key: 'Enter' })
    expect(confirm).toHaveBeenCalledTimes(2)
  })

  it('disables the action button while editing is unavailable', () => {
    render(confirmationView(vi.fn(), true))
    const button = screen.getByRole('button', { name: '确认并进入下一步' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
  })
})
