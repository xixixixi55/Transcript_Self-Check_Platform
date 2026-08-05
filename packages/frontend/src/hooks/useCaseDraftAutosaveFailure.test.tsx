import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import type { CaseDraft, ClientIdentity } from '@biji/shared/types'
import { useCaseDraftAutosave } from './useCaseDraftAutosave'

vi.mock('axios', () => ({ default: { patch: vi.fn(), get: vi.fn() } }))

const patchMock = vi.mocked(axios.patch)
const identity: ClientIdentity = { client_instance_id: 'client-synthetic', session_id: 'session-synthetic', deployment_instance_id: 'local', observed_at: '2026-01-01T00:00:00.000Z', identity_kind: 'local_session' }
const draft = (): CaseDraft => ({ case_id: 'case-synthetic', schema_version: 1, case_name: 'SYNTHETIC', case_summary: 'TEST', case_number: 'SYN-1', report: {} as CaseDraft['report'], report_version: 'legacy-v1', field_states: {}, asset_refs: [], template_ref: null, archive_plan_id: null, lifecycle: 'archive_verified', revision: 3, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' })

describe('useCaseDraftAutosave business failures', () => {
  beforeEach(() => { vi.useRealTimers(); vi.clearAllMocks() })
  afterEach(() => { vi.useRealTimers() })

  it('settles manual save when the server reports a failed draft without a saved draft', async () => {
    patchMock.mockResolvedValue({ data: { data: { draft_save_status: { status: 'failed', error_code: 'ARCHIVE_PUBLISH_FENCE_ACTIVE' }, shared_defaults_save_status: { status: 'failed', error_code: 'DRAFT_SAVE_NOT_APPLIED' }, draft: null } } })
    const view = renderHook(() => useCaseDraftAutosave({ caseId: 'case-synthetic', draft: draft(), identity, sharedValues: null, sharedDefaultsRevision: null, includeSharedDefaults: false, changeToken: 1, enabled: true, onSaved: vi.fn() }))
    let manualSave: Promise<boolean> | undefined
    await act(async () => { manualSave = view.result.current.saveNow(); await expect(manualSave).resolves.toBe(false) })
    expect(patchMock).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(view.result.current.draftState).toMatchObject({ status: 'failed', errorCode: 'ARCHIVE_PUBLISH_FENCE_ACTIVE' }))
    expect(view.result.current.hasPending).toBe(true)
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 50)) })
    expect(patchMock).toHaveBeenCalledTimes(1)
  })
})
