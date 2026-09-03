import { fireEvent, render, screen } from '@testing-library/react'
import type { InspectionReport } from '@biji/shared/types'
import { describe, expect, it, vi } from 'vitest'
import type { GuidedReviewAction } from '../hooks/useGuidedReviewCards'
import { GuidedReviewCard } from './GuidedReviewCard'

const action: GuidedReviewAction = {
  id: 'SYNTHETIC-EVIDENCE-COMPLETENESS', kind: 'pending_item', title: '请确认检材完整性',
  description: '请确认检材是否完整。',
  pendingItem: {
    id: 'SYNTHETIC-PENDING-EVIDENCE', sectionId: 'review-section-introduction',
    targetId: 'review-target-evidence-completeness', sectionLabel: '一、绪论', fieldLabel: '检材完整性',
    reason: '请确认检材是否完整。', severity: 'warning', kind: 'confirmation_required',
  },
}

function reportWithEvidence(evidenceList: InspectionReport['introduction']['evidence_list']): InspectionReport {
  return {
    title: '电子数据检查笔录', document_number: 'SYNTHETIC-DOCUMENT',
    introduction: {
      entrust_unit: 'SYNTHETIC-UNIT', entrust_persons: [], entrust_time: '', case_summary: '',
      evidence_list: evidenceList, inspection_requirement: '', inspection_time_range: '', inspectors: [], inspection_place: '',
    },
    inspection: {
      method: '', hardware_device: '', software_tools: [], process_steps: [],
      result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
    },
    attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
  }
}

describe('GuidedReviewCard evidence completeness summary', () => {
  it('shows every recognized evidence item before the user chooses complete or incomplete', () => {
    const report = reportWithEvidence([
      {
        id: 'SYNTHETIC-EVIDENCE-1', device_type: 'SYNTHETIC Phone', device_name: 'SYNTHETIC Phone', evidence_number: 'SYN-JC00000001',
        material_type: 'phone', extractable: true, imei1: 'SYNTHETIC-IMEI',
      },
      {
        id: 'SYNTHETIC-EVIDENCE-2', device_type: 'SYNTHETIC Pad', device_name: 'SYNTHETIC Pad', evidence_number: 'SYN-JC00000002',
        material_type: 'tablet', extractable: false, unextractable_reason: 'SYNTHETIC/TEST：设备损坏',
      },
    ])
    render(<GuidedReviewCard action={action} report={report} updateReport={vi.fn()}
      readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)

    expect(screen.getByRole('list', { name: '当前检材情况，共 2 项' })).toBeTruthy()
    expect(screen.getByText('SYN-JC00000001')).toBeTruthy()
    expect(screen.getByText(/SYNTHETIC Phone · 手机 · 可以提取/)).toBeTruthy()
    expect(screen.getByText('SYN-JC00000002')).toBeTruthy()
    expect(screen.getByText(/SYNTHETIC Pad · 平板 · 无法提取/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: '确认检材信息完整' })).toBeNull()
    expect(screen.getByRole('button', { name: '检材信息不完整，手工添加检材' })).toBeTruthy()
  })

  it('shows an explicit empty state before the completeness choices', () => {
    render(<GuidedReviewCard action={action} report={reportWithEvidence([])}
      updateReport={vi.fn()} readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)

    expect(screen.getByRole('status').textContent).toContain('当前未识别到检材')
    expect(screen.queryByRole('button', { name: '确认检材信息完整' })).toBeNull()
    expect(screen.getByRole('button', { name: '检材信息不完整，手工添加检材' })).toBeTruthy()
  })

  it('confirms removal of one evidence item and marks completeness unconfirmed', async () => {
    const items = [
      { id: 'SYNTHETIC-EVIDENCE-1', device_type: 'SYNTHETIC Phone', device_name: 'SYNTHETIC Phone', evidence_number: 'SYN-JC00000001' },
      { id: 'SYNTHETIC-EVIDENCE-2', device_type: 'SYNTHETIC Pad', device_name: 'SYNTHETIC Pad', evidence_number: 'SYN-JC00000002' },
    ]
    const updateReport = vi.fn()
    const onEvidenceCompletenessChange = vi.fn()
    render(<GuidedReviewCard action={action} report={reportWithEvidence(items)} updateReport={updateReport}
      readOnly={false} onEvidenceCompletenessChange={onEvidenceCompletenessChange} />)

    fireEvent.click(screen.getByRole('button', { name: '删除检材 1：SYN-JC00000001' }))
    expect(await screen.findByText('删除检材 SYN-JC00000001？')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^取\s*消$/ }))
    expect(updateReport).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: '删除检材 1：SYN-JC00000001' }))
    fireEvent.click(await screen.findByRole('button', { name: /^删\s*除$/ }))
    expect(updateReport).toHaveBeenCalledWith('introduction.evidence_list', [items[1]])
    expect(onEvidenceCompletenessChange).toHaveBeenCalledWith(false)
  })

  it('keeps deletion available during quick supplementation and disables it in read-only mode', () => {
    const report = reportWithEvidence([
      { id: 'SYNTHETIC-EVIDENCE-1', device_type: 'SYNTHETIC Phone', device_name: 'SYNTHETIC Phone', evidence_number: 'SYN-JC00000001' },
    ])
    const updateReport = vi.fn()
    const { rerender } = render(<GuidedReviewCard action={action} report={report} updateReport={updateReport}
      readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '检材信息不完整，手工添加检材' }))
    expect(screen.getByRole('textbox', { name: '快捷批量添加检材' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '删除检材 1：SYN-JC00000001' })).toBeTruthy()

    rerender(<GuidedReviewCard action={action} report={report} updateReport={updateReport}
      readOnly onEvidenceCompletenessChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: '删除检材 1：SYN-JC00000001' }).hasAttribute('disabled')).toBe(true)

    rerender(<GuidedReviewCard action={action} report={report} updateReport={updateReport}
      readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: '删除检材 1：SYN-JC00000001' }))
    fireEvent.click(screen.getByRole('button', { name: /^删\s*除$/ }))
    expect(updateReport).toHaveBeenCalledWith('introduction.evidence_list', [])
    rerender(<GuidedReviewCard action={action} report={reportWithEvidence([])} updateReport={updateReport}
      readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)
    expect(screen.getByRole('status').textContent).toContain('当前未识别到检材')
  })
})
