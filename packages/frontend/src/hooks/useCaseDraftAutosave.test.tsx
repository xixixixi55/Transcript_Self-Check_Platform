import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import type { CaseDraft, ClientIdentity } from '@biji/shared/types'
import { useCaseDraftAutosave } from './useCaseDraftAutosave'

vi.mock('axios', () => ({ default: { patch: vi.fn(), get: vi.fn() } }))

const patchMock = vi.mocked(axios.patch)
const identity: ClientIdentity = { client_instance_id: 'client-synthetic', session_id: 'session-synthetic', deployment_instance_id: 'local', observed_at: '2026-01-01T00:00:00.000Z', identity_kind: 'local_session' }
const draft = (revision = 3, report: CaseDraft['report'] = {} as CaseDraft['report']): CaseDraft => ({ case_id: 'case-synthetic', schema_version: 1, case_name: 'SYNTHETIC', case_summary: 'TEST', case_number: 'SYN-1', report, report_version: 'legacy-v1', field_states: {}, asset_refs: [], template_ref: null, archive_plan_id: null, lifecycle: 'review_ready', revision, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' })
const options = (overrides = {}) => ({ caseId: 'case-synthetic', draft: draft(), identity, sharedValues: null, sharedDefaultsRevision: null, includeSharedDefaults: false, changeToken: 1, enabled: true, onSaved: vi.fn(), ...overrides })

describe('useCaseDraftAutosave', () => {
  beforeEach(() => { vi.useRealTimers(); vi.clearAllMocks() })
  afterEach(() => { vi.useRealTimers() })

  it('debounces and advances the server revision only after a saved response', async () => {
    patchMock.mockResolvedValue({ data: { data: { draft_save_status: { status: 'saved', revision: 4 }, shared_defaults_save_status: { status: 'saved', revision: 1 }, draft: draft(4) } } })
    const opts = options()
    const view = renderHook(() => useCaseDraftAutosave(opts))
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 100)) })
    expect(patchMock).not.toHaveBeenCalled()
    await waitFor(() => expect(view.result.current.draftState.status).toBe('saved'))
    expect(patchMock).toHaveBeenCalledWith(expect.stringContaining('/workbench/cases/case-synthetic/draft'), expect.objectContaining({ expected_revision: 3 }), expect.anything())
  })

  it('surfaces a revision conflict without treating it as success', async () => {
    patchMock.mockRejectedValue({ response: { status: 409, data: { detail: { code: 'REVISION_CONFLICT', data: { draft_save_status: { status: 'conflict', error_code: 'REVISION_CONFLICT' }, shared_defaults_save_status: { status: 'failed', error_code: 'DRAFT_SAVE_NOT_APPLIED' } } } } } })
    const opts = options()
    const view = renderHook(() => useCaseDraftAutosave(opts))
    await waitFor(() => expect(view.result.current.draftState.status).toBe('conflict'))
    expect(opts.onSaved).not.toHaveBeenCalled()
  })

  it('sends structured attachment edits with the persistent case draft', async () => {
    const report = {
      attachments: {
        extract_list: { columns: ['编号', '名称'], rows: [['SYN-1', 'TEST attachment']] },
        photo_ids: ['opaque-photo-synthetic'],
        photo_groups: [{ group_id: 'group-synthetic', title: 'TEST group', asset_ids: ['opaque-photo-synthetic'] }],
        disc_number: 'SYN-001',
      },
    } as unknown as CaseDraft['report']
    patchMock.mockResolvedValue({ data: { data: { draft_save_status: { status: 'saved', revision: 4 }, shared_defaults_save_status: { status: 'not_changed' }, draft: draft(4, report) } } })
    const opts = options({ draft: draft(3, report), changeToken: 7 })
    renderHook(() => useCaseDraftAutosave(opts))
    await waitFor(() => expect(patchMock).toHaveBeenCalled())
    expect(patchMock.mock.calls[0][1]).toEqual(expect.objectContaining({
      draft: expect.objectContaining({ report: expect.objectContaining({ attachments: report.attachments }) }),
    }))
  })
})
