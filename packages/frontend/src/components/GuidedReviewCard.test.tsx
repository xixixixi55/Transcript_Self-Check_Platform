import { fireEvent, render, screen } from '@testing-library/react'
import type { InspectionReport } from '@biji/shared/types'
import { describe, expect, it, vi } from 'vitest'
import type { GuidedReviewAction } from '../hooks/useGuidedReviewCards'
import { GuidedReviewCard } from './GuidedReviewCard'

const caseSummaryAction: GuidedReviewAction = {
  id: 'pending-review-section-introduction-案件简要情况', kind: 'pending_item',
  title: '请确认案件简要情况',
  description: '报告已自动整理案件简要情况，请人工核对并按需修改。',
  advanceOnEnter: true,
  pendingItem: {
    id: 'review-section-introduction-案件简要情况', sectionId: 'review-section-introduction',
    targetId: 'review-target-case-summary', sectionLabel: '一、绪论', fieldLabel: '案件简要情况',
    reason: '报告已自动整理案件简要情况，请人工核对并按需修改。',
    severity: 'warning', kind: 'confirmation_required',
  },
}

const report = {
  title: 'SYNTHETIC/TEST RECORD', document_number: '',
  introduction: {
    entrust_unit: '', entrust_persons: [], entrust_time: '', case_summary: 'SYNTHETIC SUMMARY',
    evidence_list: [], inspection_requirement: '', inspection_time_range: '', inspectors: [],
    inspection_place: '',
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

describe('GuidedReviewCard', () => {
  it('renders the prefilled case summary as an editable multiline user input', () => {
    const updateReport = vi.fn()
    render(<GuidedReviewCard action={caseSummaryAction} report={report}
      updateReport={updateReport} readOnly={false} />)

    const input = screen.getByRole('textbox', { name: '案件简要情况' }) as HTMLTextAreaElement
    expect(input.value).toBe('SYNTHETIC SUMMARY')
    fireEvent.change(input, { target: { value: 'SYNTHETIC/TEST UPDATED SUMMARY' } })
    expect(updateReport).toHaveBeenCalledWith(
      'introduction.case_summary', 'SYNTHETIC/TEST UPDATED SUMMARY',
    )
  })
})
