import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import type { CaseDetail, CaseDraft, InspectionReport } from '@biji/shared/types'
import { useCaseRecordSession } from './useCaseRecordSession'

vi.mock('axios', () => ({ default: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }))

let detail: CaseDetail | null = null
const reloadDetail = vi.fn()
const leaseCalls: Array<{ caseId: string; enabled: boolean }> = []
const autosaveCalls: Array<{ caseId: string; draft: CaseDraft | null; enabled: boolean }> = []
const photoCalls: Array<{ caseId: string; assetRefs: unknown[] }> = []

vi.mock('./useCaseWorkbench', () => ({ useCaseWorkbench: () => ({
  detail, detailLoading: false, detailError: null, reloadDetail,
  archiveResult: vi.fn(),
}) }))
vi.mock('./useTaskRecords', () => ({ useTaskRecords: () => ({ records: {} }) }))
vi.mock('./useCompletedArchiveResult', () => ({ useCompletedArchiveResult: () => ({
  result: null, loading: false, error: null, reload: vi.fn(),
}) }))
vi.mock('./useEditLease', () => ({
  createClientIdentity: () => null,
  useEditLease: (input: { caseId: string; enabled: boolean }) => {
    leaseCalls.push(input)
    return { phase: 'active', lease: null }
  },
}))
vi.mock('./useCaseDraftAutosave', () => ({
  useCaseDraftAutosave: (input: { caseId: string; draft: CaseDraft | null; enabled: boolean }) => {
    autosaveCalls.push(input)
    return {
      draftState: { status: 'idle' }, hasPending: false, retry: vi.fn(), rebase: vi.fn(),
      reset: vi.fn(), saveNow: vi.fn(), getLastSavedDraft: vi.fn(),
    }
  },
}))
vi.mock('./useCasePhotoAssets', () => ({
  useCasePhotoAssets: (input: { caseId: string; assetRefs: unknown[] }) => {
    photoCalls.push(input)
    return { files: [], assetError: null, uploading: false, navigationUnsafe: false }
  },
}))

function caseDetail(caseId: string): CaseDetail {
  const report = {
    title: `SYNTHETIC ${caseId}`, document_number: '', introduction: { evidence_list: [] },
    inspection: {}, attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
  } as unknown as InspectionReport
  const draft = {
    schema_version: 1, case_id: caseId, case_name: `SYNTHETIC ${caseId}`,
    case_summary: 'SYNTHETIC/TEST', case_number: '', report, report_version: 'legacy-v1',
    field_states: {}, asset_refs: [], template_ref: null, archive_plan_id: null,
    lifecycle: 'review_ready', revision: 1,
    created_at: '2026-09-10T00:00:00Z', updated_at: '2026-09-10T00:00:00Z',
  } as CaseDraft
  return {
    shell: { case_id: caseId, lifecycle: 'review_ready', revision: 1 }, draft,
    source: { access_status: 'available' },
    parse_task: { task_id: `task-${caseId}`, status: 'succeeded' },
  } as unknown as CaseDetail
}

describe('useCaseRecordSession case isolation', () => {
  beforeEach(() => {
    detail = caseDetail('SYNTHETIC-CASE-A')
    leaseCalls.length = 0
    autosaveCalls.length = 0
    photoCalls.length = 0
    vi.clearAllMocks()
    vi.mocked(axios.get).mockRejectedValue(new Error('SYNTHETIC defaults unavailable'))
  })

  it('never exposes or saves the previous case draft during a reused-route transition', async () => {
    const view = renderHook(({ caseId }) => useCaseRecordSession(caseId), {
      initialProps: { caseId: 'SYNTHETIC-CASE-A' },
    })
    await waitFor(() => expect(view.result.current.report?.title).toBe('SYNTHETIC SYNTHETIC-CASE-A'))

    view.rerender({ caseId: 'SYNTHETIC-CASE-B' })

    expect(view.result.current.detail).toBeNull()
    expect(view.result.current.draft).toBeNull()
    expect(view.result.current.report).toBeNull()
    expect(view.result.current.editingEnabled).toBe(false)
    expect(leaseCalls.at(-1)).toEqual(expect.objectContaining({ caseId: 'SYNTHETIC-CASE-B', enabled: false }))
    expect(autosaveCalls.at(-1)).toEqual(expect.objectContaining({
      caseId: 'SYNTHETIC-CASE-B', draft: null, enabled: false,
    }))
    expect(photoCalls.at(-1)).toEqual(expect.objectContaining({ caseId: 'SYNTHETIC-CASE-B', assetRefs: [] }))
  })
})
