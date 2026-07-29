import type { FieldState } from '../types'
import {
  getFieldConfirmationMessage,
  getFieldSourceLabel,
  markFieldStateUserEdited,
} from './fieldProvenance'

declare const describe: (name: string, run: () => void) => void
declare const it: (name: string, run: () => void) => void
declare const expect: any

const pendingReportField: FieldState = {
  field_path: 'evidence.SYNTHETIC-evidence-2.model',
  subject_id: 'SYNTHETIC-evidence-2',
  source: 'report',
  confirmation: 'pending',
  revision: 4,
  last_changed_at: '2026-07-29T00:00:00Z',
}

describe('T007T field provenance', () => {
  it('moves user-edited fields to user source while preserving an independent pending gate', () => {
    expect(markFieldStateUserEdited(pendingReportField, '2026-07-29T00:01:00Z')).toEqual({
      ...pendingReportField,
      source: 'user',
      revision: 5,
      last_changed_at: '2026-07-29T00:01:00Z',
    })
  })

  it('provides text for pending state and a separate source label', () => {
    expect(getFieldConfirmationMessage(pendingReportField)).toBe('待人工确认')
    expect(getFieldSourceLabel('system_default')).toBe('系统默认值')
    expect(getFieldConfirmationMessage({ ...pendingReportField, confirmation: 'confirmed' })).toBeNull()
  })
})
