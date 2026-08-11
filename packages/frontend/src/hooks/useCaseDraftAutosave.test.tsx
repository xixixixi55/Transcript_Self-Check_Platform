import { act, renderHook, waitFor } from '@testing-library/react'
import { useEffect, useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import type { CaseDraft, ClientIdentity, InspectionReport } from '@biji/shared/types'
import { applyReportEdit } from '@biji/shared/utils'
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
    expect((patchMock.mock.calls[0][1] as { draft: Record<string, unknown> }).draft).not.toHaveProperty('lifecycle')
  })

  it('surfaces a revision conflict without treating it as success', async () => {
    patchMock.mockRejectedValue({ response: { status: 409, data: { detail: { code: 'REVISION_CONFLICT', data: { draft_save_status: { status: 'conflict', error_code: 'REVISION_CONFLICT' }, shared_defaults_save_status: { status: 'failed', error_code: 'DRAFT_SAVE_NOT_APPLIED' } } } } } })
    const opts = options()
    const view = renderHook(() => useCaseDraftAutosave(opts))
    await waitFor(() => expect(view.result.current.draftState.status).toBe('conflict'))
    expect(opts.onSaved).not.toHaveBeenCalled()
  })

  it('sends structured attachment edits with the persistent case draft', async () => {
    const firstMaterial = {
      id: 'SYNTHETIC-MATERIAL-1', device_type: 'phone', evidence_number: 'SYNTHETIC-1',
    }
    const secondMaterial = {
      id: 'SYNTHETIC-MATERIAL-2', device_type: 'tablet', evidence_number: 'SYNTHETIC-2',
    }
    const baseReport = {
      title: 'SYNTHETIC REPORT', document_number: 'SYNTHETIC-DOC-1',
      introduction: {
        entrust_unit: '', entrust_persons: [], entrust_time: '', case_summary: '',
        evidence_list: [firstMaterial], inspection_requirement: '', inspection_time_range: '',
        inspectors: [], inspection_place: '',
      },
      inspection: {
        method: '', hardware_device: '', software_tools: [], process_steps: [
          { step_number: 1, content: 'SYNTHETIC old material' },
          { step_number: 2, content: 'SYNTHETIC old photos' },
          { step_number: 3, content: 'SYNTHETIC environment' },
          { step_number: 4, content: 'SYNTHETIC old inspection' },
        ],
        result: { evidence_number: 'SYNTHETIC-1', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
      },
      attachments: {
        extract_list: { columns: [], rows: [] },
        photo_ids: ['opaque-photo-1-front', 'opaque-photo-1-back', 'opaque-photo-2-front', 'opaque-photo-2-back'],
        photo_groups: [{
          material_id: firstMaterial.id, material_number: firstMaterial.evidence_number,
          display_text: '检材SYNTHETIC-1照片',
          ordered_image_ids: ['opaque-photo-1-front', 'opaque-photo-1-back'], source_order: 1,
        }],
        disc_number: 'SYN-001',
      },
    } as InspectionReport
    const report = applyReportEdit(
      baseReport, 'introduction.evidence_list', [firstMaterial, secondMaterial],
    )
    patchMock.mockResolvedValue({ data: { data: { draft_save_status: { status: 'saved', revision: 4 }, shared_defaults_save_status: { status: 'not_changed' }, draft: draft(4, report) } } })
    const opts = options({ draft: draft(3, report), changeToken: 7 })
    renderHook(() => useCaseDraftAutosave(opts))
    await waitFor(() => expect(patchMock).toHaveBeenCalled())
    const savedReport = (patchMock.mock.calls[0][1] as { draft: CaseDraft }).draft.report
    expect(savedReport.attachments.photo_groups).toEqual(report.attachments.photo_groups)
    expect(savedReport.attachments.photo_groups).toHaveLength(2)
    expect(savedReport.inspection.result.evidence_number).toBe('SYNTHETIC-1、SYNTHETIC-2')
  })

  it('sends only the explicit sparse shared-default patch and treats draft success as final', async () => {
    patchMock.mockResolvedValue({ data: { data: {
      draft_save_status: { status: 'saved', revision: 4 },
      shared_defaults_save_status: { status: 'failed', error_code: 'SYNTHETIC_DEFAULT_FAILURE' },
      draft: draft(4),
    } } })
    const opts = options({
      sharedDefaultsPatch: { inspection_place: 'SYNTHETIC-PLACE' },
      sharedDefaultsRevision: 2,
      includeSharedDefaults: true,
    })
    const view = renderHook(() => useCaseDraftAutosave(opts))
    await waitFor(() => expect(view.result.current.draftState.status).toBe('saved'))
    const request = patchMock.mock.calls[0][1] as Record<string, unknown>
    expect(request.shared_defaults_patch).toEqual({ inspection_place: 'SYNTHETIC-PLACE' })
    expect(request.shared_defaults_patch).not.toHaveProperty('document_number')
    expect(view.result.current.hasPending).toBe(false)
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(patchMock).toHaveBeenCalledTimes(1)
  })

  it('does not reschedule a save when the caller clears its shared patch after success', async () => {
    patchMock.mockResolvedValue({ data: { data: {
      draft_save_status: { status: 'saved', revision: 4 },
      shared_defaults_save_status: { status: 'updated', revision: 3 },
      draft: draft(4),
    } } })
    renderHook(() => {
      const [patch, setPatch] = useState<Record<string, unknown> | null>({ inspection_place: 'SYNTHETIC-PLACE' })
      return useCaseDraftAutosave({
        ...options(),
        sharedDefaultsPatch: patch,
        sharedDefaultsRevision: 2,
        includeSharedDefaults: Boolean(patch),
        onSaved: () => setPatch(null),
      })
    })
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(patchMock).toHaveBeenCalledTimes(1)
  })

  it('settles one manual save when the caller applies the returned draft and clears the change token', async () => {
    patchMock.mockImplementation(async (_url, body) => {
      const request = body as { draft: CaseDraft }
      const savedDraft = { ...request.draft, revision: request.draft.revision + 1, updated_at: '2026-01-01T00:00:01Z' }
      return { data: { data: {
        draft_save_status: { status: 'saved', revision: savedDraft.revision },
        shared_defaults_save_status: { status: 'unchanged', revision: 0 },
        draft: savedDraft,
      } } }
    })
    const view = renderHook(() => {
      const [value, setValue] = useState(draft())
      const [token, setToken] = useState(1)
      const autosave = useCaseDraftAutosave({
        ...options(),
        draft: value,
        changeToken: token,
        onSaved: (savedDraft, _sharedStatus, meta) => {
          setValue(savedDraft)
          setToken(current => meta.hasNewerChanges ? current : 0)
        },
      })
      return { autosave, token }
    })

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(view.result.current.autosave.hasPending).toBe(false))
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(patchMock).toHaveBeenCalledTimes(1)
    expect(view.result.current.token).toBe(0)
  })

  it('does not resend an identical draft when a token changes during the request', async () => {
    patchMock.mockImplementation(async (_url, body) => {
      await new Promise(resolve => setTimeout(resolve, 100))
      const request = body as { draft: CaseDraft }
      const savedDraft = { ...request.draft, revision: request.draft.revision + 1, updated_at: '2026-01-01T00:00:01Z' }
      return { data: { data: {
        draft_save_status: { status: 'saved', revision: savedDraft.revision },
        shared_defaults_save_status: { status: 'unchanged', revision: 0 },
        draft: savedDraft,
      } } }
    })
    const view = renderHook(() => {
      const [token, setToken] = useState(1)
      useEffect(() => {
        const timer = window.setTimeout(() => setToken(2), 710)
        return () => window.clearTimeout(timer)
      }, [])
      return useCaseDraftAutosave(options({ changeToken: token }))
    })

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1), { timeout: 2000 })
    await new Promise(resolve => setTimeout(resolve, 600))
    expect(patchMock).toHaveBeenCalledTimes(1)
    expect(view.result.current.hasPending).toBe(false)
  })

  it('coalesces save-now with the same in-flight autosave request', async () => {
    let resolveRequest: ((value: unknown) => void) | undefined
    patchMock.mockImplementation(() => new Promise(resolve => { resolveRequest = resolve }))
    const view = renderHook(() => useCaseDraftAutosave(options({
      sharedDefaultsPatch: { inspection_place: 'SYNTHETIC-PLACE' },
      sharedDefaultsRevision: 2,
      includeSharedDefaults: true,
    })))

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))
    let manualSave: Promise<boolean> | undefined
    act(() => { manualSave = view.result.current.saveNow() })
    expect(patchMock).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveRequest?.({ data: { data: {
        draft_save_status: { status: 'saved', revision: 4 },
        shared_defaults_save_status: { status: 'updated', revision: 3 },
        draft: draft(4),
      } } })
      expect(await manualSave).toBe(true)
    })
    expect(view.result.current.draftState.status).toBe('saved')
    expect(patchMock).toHaveBeenCalledTimes(1)
  })

  it('waits for a newer attachment edit queued behind an in-flight save', async () => {
    const resolvers: Array<(value: unknown) => void> = []
    patchMock.mockImplementation(() => new Promise(resolve => { resolvers.push(resolve) }))
    const firstReport = { attachments: { photo_ids: ['asset-synthetic-1'] } } as CaseDraft['report']
    const secondReport = { attachments: { photo_ids: ['asset-synthetic-1', 'asset-synthetic-2'] } } as CaseDraft['report']
    const view = renderHook(
      ({ value, token }) => useCaseDraftAutosave(options({ draft: value, changeToken: token })),
      { initialProps: { value: draft(3, firstReport), token: 1 } },
    )
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))

    view.rerender({ value: draft(3, secondReport), token: 2 })
    let manualSave: Promise<boolean> | undefined
    act(() => { manualSave = view.result.current.saveNow() })
    await act(async () => {
      resolvers[0]({ data: { data: {
        draft_save_status: { status: 'saved', revision: 4 },
        shared_defaults_save_status: { status: 'unchanged', revision: 0 },
        draft: draft(4, firstReport),
      } } })
    })
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(2))
    resolvers[1]({ data: { data: {
      draft_save_status: { status: 'saved', revision: 5 },
      shared_defaults_save_status: { status: 'unchanged', revision: 0 },
      draft: draft(5, secondReport),
    } } })

    await expect(manualSave).resolves.toBe(true)
    await waitFor(() => expect(view.result.current.hasPending).toBe(false))
    expect((patchMock.mock.calls[1][1] as { expected_revision: number; draft: CaseDraft }).expected_revision).toBe(4)
    expect((patchMock.mock.calls[1][1] as { draft: CaseDraft }).draft.report).toEqual(secondReport)
  })

  it('queues a newer edit behind the in-flight draft revision', async () => {
    const resolvers: Array<(value: unknown) => void> = []
    patchMock.mockImplementation(() => new Promise(resolve => { resolvers.push(resolve) }))
    const firstReport = { title: 'SYNTHETIC-FIRST' } as CaseDraft['report']
    const secondReport = { title: 'SYNTHETIC-SECOND' } as CaseDraft['report']
    const view = renderHook(
      ({ value, token }) => useCaseDraftAutosave(options({ draft: value, changeToken: token })),
      { initialProps: { value: draft(3, firstReport), token: 1 } },
    )
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))

    view.rerender({ value: draft(3, secondReport), token: 2 })
    await act(async () => {
      resolvers[0]({ data: { data: {
        draft_save_status: { status: 'saved', revision: 4 },
        shared_defaults_save_status: { status: 'unchanged', revision: 0 },
        draft: draft(4, firstReport),
      } } })
    })

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(2))
    const queuedRequest = patchMock.mock.calls[1][1] as { expected_revision: number; draft: CaseDraft }
    expect(queuedRequest.expected_revision).toBe(4)
    expect(queuedRequest.draft.report.title).toBe('SYNTHETIC-SECOND')
    await act(async () => {
      resolvers[1]({ data: { data: {
        draft_save_status: { status: 'saved', revision: 5 },
        shared_defaults_save_status: { status: 'unchanged', revision: 0 },
        draft: draft(5, secondReport),
      } } })
    })
    await waitFor(() => expect(view.result.current.hasPending).toBe(false))
  })
})
