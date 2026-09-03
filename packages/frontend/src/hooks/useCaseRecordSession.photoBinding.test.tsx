import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type {
  CaseDetail, CaseDraft, ClientIdentity, EditLease, EvidenceItem,
  InspectionReport, OpaqueAssetRef, SharedDefaults,
} from '@biji/shared/types'
import { useCaseRecordSession } from './useCaseRecordSession'
import { EVIDENCE_COMPLETENESS_FIELD_PATH } from './useReviewChecklist'

vi.mock('axios', () => ({ default: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }))
vi.mock('./useCaseWorkbench', () => ({ useCaseWorkbench: () => ({
  detail: testDetail, reloadDetail: vi.fn(), archiveResult: null,
}) }))
vi.mock('./useEditLease', () => ({
  createClientIdentity: () => testIdentity,
  useEditLease: () => ({ phase: 'active', lease: testLease }),
}))
vi.mock('./useTaskRecords', () => ({ useTaskRecords: () => ({ records: {} }) }))
vi.mock('./useCompletedArchiveResult', () => ({ useCompletedArchiveResult: () => null }))
vi.mock('./useCasePhotoAssets', () => ({ useCasePhotoAssets: () => ({
  files: [], assetError: null, uploading: false, navigationUnsafe: false,
  handleChange: vi.fn(), readFiles: vi.fn(), waitForIdle: vi.fn(),
}) }))

const caseId = 'case-synthetic-photo-rebase'
const testIdentity: ClientIdentity = {
  client_instance_id: 'client-synthetic', session_id: 'session-synthetic',
  deployment_instance_id: 'deployment-synthetic', observed_at: '2026-01-01T00:00:00Z',
  identity_kind: 'local_session',
}
const testDefaults: SharedDefaults = {
  schema_version: 1, deployment_instance_id: 'deployment-synthetic', revision: 0,
  document_number: '', inspection_place: '', inspection_method: '',
  hardware_device: '', inspector_order: [], disc_number_prefix: 'GP',
  migration_decision: 'ignored', updated_at: '2026-01-01T00:00:00Z',
}
const testLease: EditLease = {
  schema_version: 1, lease_id: 'lease-synthetic', case_id: caseId,
  session_id: testIdentity.session_id, client_instance_id: testIdentity.client_instance_id,
  lease_token: 'token-synthetic', last_heartbeat_at: '2026-01-01T00:00:00Z',
  expires_at: '2026-01-01T00:02:00Z', status: 'active', revision: 0,
}
const firstRef: OpaqueAssetRef = {
  asset_id: 'asset-synthetic-first', asset_kind: 'image', fingerprint: 'a'.repeat(64), metadata: {},
}
const secondRef: OpaqueAssetRef = {
  asset_id: 'asset-synthetic-second', asset_kind: 'image', fingerprint: 'b'.repeat(64), metadata: {},
}
const manualMaterial: EvidenceItem = {
  id: 'material-synthetic-manual', evidence_number: 'SYN-MANUAL-3', device_type: '',
  material_type: 'phone', material_type_status: 'confirmed_by_user', material_type_source: 'user',
}
const report: InspectionReport = {
  title: 'SYNTHETIC RECORD', document_number: 'SYN-001', case_number: 'SYN-CASE-001',
  introduction: {
    entrust_unit: 'SYNTHETIC UNIT', entrust_persons: [], entrust_time: '2026年1月1日',
    case_summary: 'SYNTHETIC/TEST', evidence_list: [], inspection_requirement: 'SYNTHETIC',
    inspection_time_range: '2026年1月1日10点00分至2026年1月1日11点00分', inspectors: [],
    inspection_place: 'SYNTHETIC PLACE',
  },
  inspection: {
    method: 'SYNTHETIC METHOD', hardware_device: 'SYNTHETIC DEVICE', software_tools: [], process_steps: [],
    result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [firstRef.asset_id], disc_number: 'GP20260101-001' },
}
const draft: CaseDraft = {
  schema_version: 1, case_id: caseId, case_name: 'SYNTHETIC CASE', case_summary: 'SYNTHETIC/TEST',
  case_number: 'SYN-CASE-001', report, report_version: 'legacy-v1', field_states: {}, asset_refs: [firstRef],
  template_ref: null, archive_plan_id: null, lifecycle: 'review_ready', revision: 4,
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}
const testDetail = {
  shell: { case_id: caseId, lifecycle: 'review_ready', revision: 1 }, draft,
  source: { access_status: 'available' }, parse_task: { task_id: 'task-synthetic', status: 'succeeded' },
} as unknown as CaseDetail

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((accept, decline) => { resolve = accept; reject = decline })
  return { promise, resolve, reject }
}

function reportWith(materials: EvidenceItem[], refs: OpaqueAssetRef[]): InspectionReport {
  return {
    ...report,
    introduction: { ...report.introduction, evidence_list: materials },
    attachments: { ...report.attachments, photo_ids: refs.map(ref => ref.asset_id) },
  }
}

function savedDraftResponse(savedDraft: CaseDraft) {
  return { data: { data: {
    draft_save_status: { status: 'saved', revision: savedDraft.revision },
    shared_defaults_save_status: { status: 'unchanged', revision: 0 },
    draft: savedDraft,
  } } }
}

function conflictResponse() {
  return { response: { data: { detail: { data: {
    draft_save_status: { status: 'conflict', error_code: 'REVISION_CONFLICT' },
    shared_defaults_save_status: { status: 'unchanged', revision: 0 }, draft: null,
  } } } } }
}

describe('useCaseRecordSession photo binding coordination', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(axios.get).mockResolvedValue({ data: { data: testDefaults } } as never)
  })

  it('rebases a pending manual material after photo binding wins the revision race', async () => {
    const staleDraftSave = deferred<unknown>()
    const photoBinding = deferred<unknown>()
    const rebasedDraftSave = deferred<unknown>()
    const draftBodies: Array<{ draft: CaseDraft; expected_revision: number }> = []
    vi.mocked(axios.patch).mockImplementation((url, body) => {
      if (url === API_ENDPOINTS.WORKBENCH_DRAFT(caseId)) {
        draftBodies.push(body as { draft: CaseDraft; expected_revision: number })
        return (draftBodies.length === 1 ? staleDraftSave.promise : rebasedDraftSave.promise) as never
      }
      if (url === API_ENDPOINTS.WORKBENCH_CASE_PHOTO_BINDING(caseId)) return photoBinding.promise as never
      throw new Error(`unexpected PATCH ${url}`)
    })
    const view = renderHook(() => useCaseRecordSession(caseId))
    await waitFor(() => expect(view.result.current.report).not.toBeNull())
    act(() => {
      view.result.current.updateReport('introduction.evidence_list', [manualMaterial])
      view.result.current.setEvidenceCompletenessConfirmed(true)
    })
    await waitFor(() => expect(draftBodies).toHaveLength(1), { timeout: 2500 })

    let bindingPromise!: Promise<boolean>
    act(() => { bindingPromise = view.result.current.updatePhotoAssetRefs([firstRef, secondRef], [firstRef]) })
    await waitFor(() => expect(axios.patch).toHaveBeenCalledWith(
      API_ENDPOINTS.WORKBENCH_CASE_PHOTO_BINDING(caseId), expect.anything(),
    ))
    const boundDraft = {
      ...draft, report: reportWith([], [firstRef, secondRef]), asset_refs: [firstRef, secondRef],
      revision: 5, updated_at: '2026-01-01T00:00:01Z',
    }
    await act(async () => {
      photoBinding.resolve({ data: { data: { draft: boundDraft } } })
      await bindingPromise
    })
    await act(async () => { staleDraftSave.reject(conflictResponse()) })
    await waitFor(() => expect(draftBodies).toHaveLength(2))
    expect(draftBodies[1]).toEqual(expect.objectContaining({
      expected_revision: 5,
      draft: expect.objectContaining({
        asset_refs: [firstRef, secondRef],
        report: expect.objectContaining({
          introduction: expect.objectContaining({ evidence_list: [manualMaterial] }),
          attachments: expect.objectContaining({ photo_ids: [firstRef.asset_id, secondRef.asset_id] }),
        }),
        field_states: expect.objectContaining({
          [EVIDENCE_COMPLETENESS_FIELD_PATH]: expect.objectContaining({ confirmation: 'confirmed' }),
        }),
      }),
    }))
    const finalDraft = {
      ...draftBodies[1].draft, revision: 6, updated_at: '2026-01-01T00:00:02Z',
    }
    await act(async () => { rebasedDraftSave.resolve(savedDraftResponse(finalDraft)) })
    await waitFor(() => expect(view.result.current.draft?.revision).toBe(6))
    expect(view.result.current.draft?.asset_refs).toEqual([firstRef, secondRef])
    expect(view.result.current.report?.introduction.evidence_list).toEqual([manualMaterial])
    expect(view.result.current.draft?.field_states[EVIDENCE_COMPLETENESS_FIELD_PATH]?.confirmation).toBe('confirmed')
    expect(view.result.current.autosave.draftState.status).toBe('saved')
  })

  it('keeps the saved material when its draft request wins before photo binding', async () => {
    const draftSave = deferred<unknown>()
    const photoBinding = deferred<unknown>()
    const draftBodies: Array<{ draft: CaseDraft; expected_revision: number }> = []
    vi.mocked(axios.patch).mockImplementation((url, body) => {
      if (url === API_ENDPOINTS.WORKBENCH_DRAFT(caseId)) {
        draftBodies.push(body as { draft: CaseDraft; expected_revision: number })
        return draftSave.promise as never
      }
      if (url === API_ENDPOINTS.WORKBENCH_CASE_PHOTO_BINDING(caseId)) return photoBinding.promise as never
      throw new Error(`unexpected PATCH ${url}`)
    })
    const view = renderHook(() => useCaseRecordSession(caseId))
    await waitFor(() => expect(view.result.current.report).not.toBeNull())
    act(() => view.result.current.updateReport('introduction.evidence_list', [manualMaterial]))
    await waitFor(() => expect(draftBodies).toHaveLength(1), { timeout: 2500 })

    let bindingPromise!: Promise<boolean>
    act(() => { bindingPromise = view.result.current.updatePhotoAssetRefs([firstRef, secondRef], [firstRef]) })
    const materialDraft = {
      ...draftBodies[0].draft, revision: 5, updated_at: '2026-01-01T00:00:01Z',
    }
    await act(async () => { draftSave.resolve(savedDraftResponse(materialDraft)) })
    await waitFor(() => expect(view.result.current.draft?.revision).toBe(5))
    const boundDraft = {
      ...materialDraft, report: reportWith([manualMaterial], [firstRef, secondRef]),
      asset_refs: [firstRef, secondRef], revision: 6, updated_at: '2026-01-01T00:00:02Z',
    }
    await act(async () => {
      photoBinding.resolve({ data: { data: { draft: boundDraft } } })
      await bindingPromise
    })
    await waitFor(() => expect(view.result.current.draft?.revision).toBe(6))
    expect(draftBodies).toHaveLength(1)
    expect(view.result.current.draft?.asset_refs).toEqual([firstRef, secondRef])
    expect(view.result.current.report?.introduction.evidence_list).toEqual([manualMaterial])
  })
})
