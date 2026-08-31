import { render, screen } from '@testing-library/react'
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
    expect(screen.getByRole('button', { name: '确认检材信息完整' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '检材信息不完整，手工添加检材' })).toBeTruthy()
  })

  it('shows an explicit empty state before the completeness choices', () => {
    render(<GuidedReviewCard action={action} report={reportWithEvidence([])}
      updateReport={vi.fn()} readOnly={false} onEvidenceCompletenessChange={vi.fn()} />)

    expect(screen.getByRole('status').textContent).toContain('当前未识别到检材')
    expect(screen.getByRole('button', { name: '确认检材信息完整' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '检材信息不完整，手工添加检材' })).toBeTruthy()
  })
})
