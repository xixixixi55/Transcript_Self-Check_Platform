import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { CaseDetail, CaseDraft, CaseShell, ClientIdentity, EditLease, InspectionReport, SharedDefaults, SourceRecord, TaskRecord } from '@biji/shared/types'
import CaseRecordGeneratePage from './CaseRecordGeneratePage'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const postMock = vi.mocked(axios.post)
const patchMock = vi.mocked(axios.patch)
const caseId = 'case-synthetic-archive-race'
const identity: ClientIdentity = { client_instance_id: 'client-synthetic', session_id: 'session-synthetic', deployment_instance_id: 'synthetic-uat', observed_at: '2026-01-01T00:00:00Z', identity_kind: 'local_session' }
const defaults: SharedDefaults = { schema_version: 1, deployment_instance_id: 'synthetic-uat', revision: 0, document_number: '', inspection_place: '', inspection_method: '', hardware_device: '', inspector_order: [], disc_number_prefix: 'GP', migration_decision: 'ignored', updated_at: '2026-01-01T00:00:00Z' }
const task: TaskRecord = { schema_version: 1, task_id: 'task-synthetic-parse', case_id: caseId, kind: 'parse', status: 'succeeded', stage: 'parse', percent: 100, counters: {}, input_revision: 0, attempt: 1, cancel_requested: false, revision: 0, created_at: '2026-01-01T00:00:00Z', finished_at: '2026-01-01T00:00:00Z' }
const lease: EditLease = { schema_version: 1, lease_id: 'lease-synthetic', case_id: caseId, session_id: identity.session_id, client_instance_id: identity.client_instance_id, lease_token: 'token-synthetic', last_heartbeat_at: '2026-01-01T00:00:00Z', expires_at: '2026-01-01T00:02:00Z', status: 'active', takeover_of_lease_id: null, revision: 0 }

function report(discNumber = 'GP20260731-001'): InspectionReport {
  return {
    title: '电子数据检查笔录', document_number: 'SYN-TEST〔2026〕001号', case_number: 'SYN-CASE-001',
    introduction: { entrust_unit: 'SYNTHETIC-UNIT', entrust_persons: ['SYNTHETIC-PERSON'], entrust_time: '2026年7月31日', case_summary: 'SYNTHETIC/TEST', evidence_list: [], inspection_requirement: 'SYNTHETIC-REQUIREMENT', inspection_time_range: '2026年7月31日10点00分至2026年7月31日11点00分', inspectors: [], inspection_place: 'SYNTHETIC-PLACE' },
    inspection: { method: 'SYNTHETIC-METHOD', hardware_device: 'SYNTHETIC-DEVICE', software_tools: [], process_steps: [], result: { evidence_number: 'SYN-1', software_name: 'SYNTHETIC-TOOL', software_version: '1.0', data_summary: 'SYNTHETIC-DATA', rar_filename: '', md5_hash: '', file_size: '' } },
    attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: discNumber },
  }
}

function detail(shellRevision: number, draftRevision: number, lifecycle: CaseShell['lifecycle'] = 'review_ready', discNumber = 'GP20260731-001'): CaseDetail {
  const draft: CaseDraft = { schema_version: 1, case_id: caseId, case_name: 'SYNTHETIC-CASE', case_summary: 'SYNTHETIC/TEST', case_number: 'SYN-CASE-001', report: report(discNumber), report_version: 'legacy-v1', field_states: {}, asset_refs: [], template_ref: null, archive_plan_id: null, lifecycle: lifecycle === 'archive_queued' ? 'review_ready' : lifecycle, revision: draftRevision, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
  const shell: CaseShell = { schema_version: 1, case_id: caseId, case_name: 'SYNTHETIC-CASE', case_summary: 'SYNTHETIC/TEST', case_number: 'SYN-CASE-001', source_id: 'source-synthetic', parse_task_id: task.task_id, lifecycle, report_available: true, revision: shellRevision, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
  const source: SourceRecord = { schema_version: 1, source_id: 'source-synthetic', source_type: 'report_directory', case_id: caseId, allowed_root_id: 'root-synthetic', metadata: {}, fingerprint: 'fingerprint-synthetic', access_status: 'available', requires_reselection: false, revalidation_error_code: null, last_verified_at: '2026-01-01T00:00:00Z', revision: 0 }
  return { shell, draft, source, parse_task: task }
}

describe('CaseRecordGeneratePage archive decision coordination', () => {
  let detailReads = 0
  let decisionBodies: Record<string, unknown>[] = []
  let events: string[] = []
  let rejectSave = false
  let failSharedDefaults = false
  let conflictDecision = false
  let holdSave = false
  let resolveSave: (() => void) | null = null
  beforeAll(() => { Object.defineProperty(window, 'matchMedia', { writable: true, value: () => ({ matches: false, media: '', onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() }) }) })
  beforeEach(() => {
    vi.clearAllMocks(); detailReads = 0; decisionBodies = []; events = []; rejectSave = false; failSharedDefaults = false; conflictDecision = false; holdSave = false; resolveSave = null
    getMock.mockImplementation(async (url: string) => {
      if (url === API_ENDPOINTS.WORKBENCH_DEFAULTS) return { data: { data: defaults } }
      if (url === API_ENDPOINTS.WORKBENCH_CASE(caseId)) { const read = detailReads++; return { data: { data: read === 0 ? detail(5, 5) : read === 1 ? detail(6, 6, 'review_ready', 'GP20260731-002') : detail(7, 6, 'archive_queued', 'GP20260731-002') } } }
      if (url === API_ENDPOINTS.WORKBENCH_TASK(task.task_id)) return { data: { data: task } }
      if (url === API_ENDPOINTS.WORKBENCH_CASE_ASSETS(caseId)) return { data: { data: { items: [] } } }
      if (url === API_ENDPOINTS.WORKBENCH_TEMPLATES || url === API_ENDPOINTS.DEVICES) return { data: { data: [] } }
      if (url === API_ENDPOINTS.INSPECTORS) return { data: { data: [] } }
      throw new Error(`unexpected GET ${url}`)
    })
    postMock.mockImplementation(async (url: string, body?: unknown) => {
      if (url === API_ENDPOINTS.WORKBENCH_LEASE(caseId)) return { data: { data: lease } }
      if (url === API_ENDPOINTS.WORKBENCH_LEASE_RELEASE(lease.lease_id)) return { data: { data: lease } }
      if (url === API_ENDPOINTS.WORKBENCH_ARCHIVE_DECISION(caseId)) {
        events.push('archive-decision'); decisionBodies.push(body as Record<string, unknown>)
        if (conflictDecision) throw { response: { status: 409, data: { detail: { code: 'REVISION_CONFLICT', message: '案件已被其他会话修改。' } } } }
        if (body && (body as Record<string, unknown>).expected_revision !== 6) throw { response: { status: 409, data: { detail: { code: 'REVISION_CONFLICT', message: '案件已被其他会话修改。' } } } }
        return { data: { data: { case: detail(7, 6, 'archive_queued', 'GP20260731-002'), decision: 'immediate', archive_status: 'archive_task_queued', archive_task: { task_id: 'archive-synthetic-1' } } } }
      }
      if (url === API_ENDPOINTS.EXPORT_RECORD) return { data: new Blob(['SYNTHETIC-DOCX']) }
      return { data: { data: {} } }
    })
    patchMock.mockImplementation(async (_url: string, body: unknown) => {
      events.push('draft-save')
      if (rejectSave) throw new Error('SYNTHETIC_SAVE_FAILED')
      const request = body as { draft: CaseDraft }
      const sharedDefaultsSaveStatus = failSharedDefaults
        ? { status: 'failed', revision: 0, error_code: 'SYNTHETIC_DEFAULT_FAILURE' }
        : { status: 'unchanged', revision: 0 }
      const savedResponse = { data: { data: { draft_save_status: { status: 'saved', revision: 6 }, shared_defaults_save_status: sharedDefaultsSaveStatus, draft: { ...request.draft, lifecycle: 'review_ready', revision: 6, updated_at: '2026-01-01T00:00:01Z' } } } }
      if (holdSave) return new Promise(resolve => { resolveSave = () => resolve(savedResponse) })
      return savedResponse
    })
  })

  function renderPage() {
    return render(<MemoryRouter initialEntries={[`/electronic-inspection/cases/${caseId}`]}><Routes><Route path="/electronic-inspection/cases/:caseId" element={<CaseRecordGeneratePage />} /></Routes></MemoryRouter>)
  }

  async function editDiscNumber() {
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_LEASE(caseId), expect.anything()))
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: /GP20260731-001/ }))
    const input = await screen.findByDisplayValue('GP20260731-001')
    fireEvent.change(input, { target: { value: 'GP20260731-002' } })
    fireEvent.blur(input)
  }

  async function editDiscAndClick() {
    await editDiscNumber()
    fireEvent.click(screen.getByRole('button', { name: /立即开始压缩/ }))
  }

  it('persists an immediate disc-number edit before posting one archive decision with the new shell revision', async () => {
    renderPage(); await editDiscAndClick()
    await waitFor(() => expect(decisionBodies).toHaveLength(1))
    expect(events.indexOf('draft-save')).toBeGreaterThanOrEqual(0)
    expect(events.indexOf('draft-save')).toBeLessThan(events.indexOf('archive-decision'))
    expect(decisionBodies[0].expected_revision).toBe(6)
    expect(patchMock).toHaveBeenCalledTimes(1)
    expect(postMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_ARCHIVE_DECISION(caseId))).toHaveLength(1)
  }, 15000)

  it('does not create an archive task when draft persistence fails or a real revision conflict remains', async () => {
    rejectSave = true; const failedView = renderPage(); await editDiscAndClick()
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))
    expect(decisionBodies).toHaveLength(0)

    failedView.unmount()
    conflictDecision = true; rejectSave = false; detailReads = 0; renderPage(); await editDiscAndClick()
    await waitFor(() => expect(decisionBodies).toHaveLength(1))
    expect(await screen.findByText(/其他会话修改/)).toBeTruthy()
    expect(postMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_ARCHIVE_DECISION(caseId))).toHaveLength(1)
  }, 15000)

  it('waits for an in-flight save and coalesces rapid immediate clicks into one decision', async () => {
    holdSave = true; renderPage(); await editDiscAndClick()
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole('button', { name: /立即开始压缩/ }))
    expect(decisionBodies).toHaveLength(0)
    holdSave = false; resolveSave?.(); resolveSave = null
    await waitFor(() => expect(decisionBodies).toHaveLength(1))
    expect(decisionBodies[0].expected_revision).toBe(6)
    expect(patchMock).toHaveBeenCalledTimes(1)
    expect(postMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_ARCHIVE_DECISION(caseId))).toHaveLength(1)
  }, 15000)

  it('allows Word export after the draft saves even when shared defaults fail', async () => {
    failSharedDefaults = true
    const previousCreateObjectUrl = window.URL.createObjectURL
    const previousRevokeObjectUrl = window.URL.revokeObjectURL
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:synthetic') })
    Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    try {
      renderPage()
      await editDiscNumber()
      await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))
      expect(await screen.findByText('草稿已保存，共享默认值更新失败。')).toBeTruthy()

      fireEvent.click(screen.getByRole('button', { name: /导出 Word/ }))
      fireEvent.click(await screen.findByRole('button', { name: '开始导出' }))
      await waitFor(() => expect(postMock.mock.calls.some(([url]) => url === API_ENDPOINTS.EXPORT_RECORD)).toBe(true))
      const exportCall = postMock.mock.calls.find(([url]) => url === API_ENDPOINTS.EXPORT_RECORD)
      const formData = exportCall?.[1] as FormData
      expect(formData.get('case_id')).toBe(caseId)
      expect(formData.get('case_revision')).toBe('6')
    } finally {
      anchorClick.mockRestore()
      Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: previousCreateObjectUrl })
      Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: previousRevokeObjectUrl })
    }
  }, 15000)
})
