import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import axios from 'axios'
import { API_ENDPOINTS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import { unifiedExportRequestTimeoutMs } from '@biji/shared/utils'
import type { ArchiveTaskCardSummary, ArchiveTaskResult, CaseDetail, CaseDraft, CaseShell, ClientIdentity, EditLease, InspectionReport, SharedDefaults, SourceRecord, TaskRecord } from '@biji/shared/types'
import CaseRecordGeneratePage from './CaseRecordGeneratePage'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const postMock = vi.mocked(axios.post)
const patchMock = vi.mocked(axios.patch)
const caseId = 'case-synthetic-archive-race'
const identity: ClientIdentity = { client_instance_id: 'client-synthetic', session_id: 'session-synthetic', deployment_instance_id: 'synthetic-uat', observed_at: '2026-01-01T00:00:00Z', identity_kind: 'local_session' }
const defaults: SharedDefaults = { schema_version: 1, deployment_instance_id: 'synthetic-uat', revision: 0, document_number: '', inspection_place: '', inspection_method: '', hardware_device: '', inspector_order: [], disc_number_prefix: 'GP', migration_decision: 'ignored', updated_at: '2026-01-01T00:00:00Z' }
const availableInspector = { id: 'inspector-synthetic', name: '张三', unit: 'SYNTHETIC-UNIT', police_number: 'SYN-001', enabled: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
const task: TaskRecord = { schema_version: 1, task_id: 'task-synthetic-parse', case_id: caseId, kind: 'parse', status: 'succeeded', stage: 'parse', percent: 100, counters: {}, input_revision: 0, attempt: 1, cancel_requested: false, revision: 0, created_at: '2026-01-01T00:00:00Z', finished_at: '2026-01-01T00:00:00Z' }
const archiveTaskSummary: ArchiveTaskCardSummary = {
  progress_kind: 'workflow_milestone', stage: 'completed', stage_label: '归档完成', stage_index: 7,
  stage_count: 7, percent: 100, updated_at: '2026-01-01T00:00:00Z', last_heartbeat_at: null,
  output_bytes: 579, output_volume_count: 2, last_output_change_at: null, worker_state: 'released',
  task_id: 'archive-synthetic-1', case_id: caseId, status: 'succeeded', started_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:00:10Z', error_summary: null, allowed_actions: ['view_result'],
}
const completedArchiveResult: ArchiveTaskResult = {
  task_id: archiveTaskSummary.task_id, case_id: caseId, manifest_id: 'manifest-synthetic',
  plan_row_revision: 4, verified_slots: [], assets: [],
  parts: [
    { part_id: 'part-1', filename: '合成案件.part1.rar', size_bytes: 123, md5: 'a'.repeat(32), disc_number: 'GP20260731-01', disc_date: '2026-07-31' },
    { part_id: 'part-2', filename: '合成案件.part2.rar', size_bytes: 456, md5: 'b'.repeat(32), disc_number: 'GP20260731-02', disc_date: '2026-07-31' },
  ],
  finished_at: archiveTaskSummary.finished_at,
}
const lease: EditLease = { schema_version: 1, lease_id: 'lease-synthetic', case_id: caseId, session_id: identity.session_id, client_instance_id: identity.client_instance_id, lease_token: 'token-synthetic', last_heartbeat_at: '2026-01-01T00:00:00Z', expires_at: '2026-01-01T00:02:00Z', status: 'active', takeover_of_lease_id: null, revision: 0 }

function report(discNumber = 'GP20260731-001'): InspectionReport {
  return {
    title: '电子数据检查笔录', document_number: 'SYN-TEST〔2026〕001号', case_number: 'SYN-CASE-001',
    introduction: { entrust_unit: 'SYNTHETIC-UNIT', entrust_persons: ['SYNTHETIC-PERSON'], entrust_time: '2026年7月31日', case_summary: 'SYNTHETIC/TEST', evidence_list: [], inspection_requirement: 'SYNTHETIC-REQUIREMENT', inspection_time_range: '2026年7月31日10点00分至2026年7月31日11点00分', inspectors: [], inspection_place: 'SYNTHETIC-PLACE' },
    inspection: { method: 'SYNTHETIC-METHOD', hardware_device: 'SYNTHETIC-DEVICE', software_tools: [], process_steps: [], result: { evidence_number: 'SYN-1', software_name: 'SYNTHETIC-TOOL', software_version: '1.0', data_summary: 'SYNTHETIC-DATA', rar_filename: '', md5_hash: '', file_size: '' } },
    attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: discNumber },
  }
}

function detail(shellRevision: number, draftRevision: number, lifecycle: CaseShell['lifecycle'] = 'review_ready', discNumber = 'GP20260731-001', archiveSummary: ArchiveTaskCardSummary | null = null): CaseDetail {
  const draft: CaseDraft = { schema_version: 1, case_id: caseId, case_name: 'SYNTHETIC-CASE', case_summary: 'SYNTHETIC/TEST', case_number: 'SYN-CASE-001', report: report(discNumber), report_version: 'legacy-v1', field_states: {}, asset_refs: [], template_ref: null, archive_plan_id: null, lifecycle: lifecycle === 'archive_queued' ? 'review_ready' : lifecycle, revision: draftRevision, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
  const shell: CaseShell = { schema_version: 1, case_id: caseId, case_name: 'SYNTHETIC-CASE', case_summary: 'SYNTHETIC/TEST', case_number: 'SYN-CASE-001', source_id: 'source-synthetic', parse_task_id: task.task_id, lifecycle, report_available: true, revision: shellRevision, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', archive_task_summary: archiveSummary }
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
  let showCompletedArchive = false
  let useExportedLifecycle = false
  let sourcePending = false
  let recoverPhotoOnLoad = false
  let initialLifecycle: CaseShell['lifecycle'] = 'review_ready'
  let resolveSave: (() => void) | null = null
  let archiveResultParts: ArchiveTaskResult['parts'] | null = null
  beforeAll(() => { Object.defineProperty(window, 'matchMedia', { writable: true, value: () => ({ matches: false, media: '', onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() }) }) })
  beforeEach(() => {
    vi.clearAllMocks(); detailReads = 0; decisionBodies = []; events = []; rejectSave = false; failSharedDefaults = false; conflictDecision = false; holdSave = false; showCompletedArchive = false; useExportedLifecycle = false; sourcePending = false; recoverPhotoOnLoad = false; initialLifecycle = 'review_ready'; resolveSave = null; archiveResultParts = null
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getMock.mockImplementation(async (url: string) => {
      if (url === API_ENDPOINTS.WORKBENCH_DEFAULTS) return { data: { data: defaults } }
      if (url === API_ENDPOINTS.WORKBENCH_CASE(caseId)) {
        const read = detailReads++
        const value = useExportedLifecycle ? detail(5, 5, 'exported', 'GP20260731-001', archiveTaskSummary) : showCompletedArchive ? detail(5, 5, 'archive_verified', 'GP20260731-001', archiveTaskSummary) : initialLifecycle !== 'review_ready' ? detail(5, 5, initialLifecycle) : read === 0 ? detail(5, 5) : read === 1 ? detail(6, 6, 'review_ready', 'GP20260731-002') : detail(7, 6, 'archive_queued', 'GP20260731-002')
        if (sourcePending) {
          value.source.access_status = 'pending'
          value.source.fingerprint = 'pending:source-synthetic'
          value.source.last_verified_at = null
        }
        return { data: { data: value } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_TASK(task.task_id)) return { data: { data: task } }
      if (url === API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT(archiveTaskSummary.task_id)) {
        return { data: { data: { ...completedArchiveResult, parts: archiveResultParts ?? completedArchiveResult.parts } } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_CASE_ASSETS(caseId)) return { data: { data: { items: recoverPhotoOnLoad ? [{ asset_id: 'asset-synthetic-recovered', asset_kind: 'image', fingerprint: 'a'.repeat(64), metadata: { file_name: 'SYNTHETIC-recovered.png', extension: '.png', media_type: 'image/png', size_bytes: 1 }, content_status: 'available' }] : [] } } }
      if (url === API_ENDPOINTS.DEVICES) return { data: { data: [] } }
      if (url === API_ENDPOINTS.INSPECTORS) return { data: { data: [availableInspector] } }
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
      if (url === API_ENDPOINTS.WORKBENCH_ARCHIVE_DISC_MAPPING(caseId)) {
        const request = body as { expected_revision: number; expected_plan_row_revision: number; first_disc_number: string }
        archiveResultParts = completedArchiveResult.parts.map((part, index) => ({
          ...part,
          disc_number: index === 0 ? request.first_disc_number : 'GP20260731-02',
          disc_date: '2026-07-31',
        }))
        return { data: { data: { case_id: caseId, task_id: 'archive-synthetic-1', expected_revision: request.expected_revision, plan_row_revision: request.expected_plan_row_revision + 1, lifecycle: 'archive_verified', prefix: 'GP', disc_date: '2026-07-31', parts: archiveResultParts.map((part, index) => ({ part_number: index + 1, disc_number: part.disc_number, disc_date: part.disc_date })) } } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY) return { data: { data: { path: 'D:\\SYNTHETIC\\EXPORT', token: 'token-synthetic' } } }
      if (url === API_ENDPOINTS.WORKBENCH_UNIFIED_EXPORT(caseId)) {
        const request = body as { expected_revision: number; export_path: string; directory_token: string }
        return { data: { data: { case_id: caseId, task_id: 'archive-synthetic-1', expected_revision: request.expected_revision, lifecycle: 'exported', output: { export_path: request.export_path, word_filename: 'SYNTHETIC.docx', rar_filenames: ['SYNTHETIC.part1.rar'], hash_verification_image: 'SYNTHETIC-hashes.png', exported_at: '2026-01-01T00:00:00Z' } } } }
      }
      return { data: { data: {} } }
    })
    patchMock.mockImplementation(async (_url: string, body: unknown) => {
      events.push('draft-save')
      if (rejectSave) throw new Error('SYNTHETIC_SAVE_FAILED')
      const request = body as { draft: CaseDraft; shared_defaults_patch?: Record<string, unknown> | null }
      const sharedDefaultsSaveStatus = failSharedDefaults
        ? { status: 'failed', revision: 0, error_code: 'SYNTHETIC_DEFAULT_FAILURE' }
        : request.shared_defaults_patch
          ? { status: 'updated', revision: 1 }
          : { status: 'unchanged', revision: 0 }
      const savedResponse = { data: { data: { draft_save_status: { status: 'saved', revision: 6 }, shared_defaults_save_status: sharedDefaultsSaveStatus, draft: { ...request.draft, lifecycle: 'review_ready', revision: 6, updated_at: '2026-01-01T00:00:01Z' } } } }
      if (holdSave) return new Promise(resolve => { resolveSave = () => resolve(savedResponse) })
      return savedResponse
    })
  })

  function renderPage() {
    const router = createMemoryRouter([
      { path: '/electronic-inspection/workbench', element: <div>工作台路由</div> },
      { path: '/electronic-inspection/cases/:caseId', element: <CaseRecordGeneratePage /> },
    ], {
      initialEntries: ['/electronic-inspection/workbench', `/electronic-inspection/cases/${caseId}`],
      initialIndex: 1,
    })
    return { ...render(<RouterProvider router={router} />), router }
  }

  async function editDiscNumber() {
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_LEASE(caseId), expect.anything()))
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    const input = await screen.findByRole('textbox', { name: '首个光盘编号' })
    expect((input as HTMLInputElement).value).toBe('GP20260731-001')
    fireEvent.change(input, { target: { value: 'GP20260731-002' } })
  }

  async function editDiscAndClick() {
    await editDiscNumber()
    fireEvent.click(screen.getByRole('button', { name: /立即开始压缩/ }))
  }

  it('shows the direct compression decision while bounded source review is pending', async () => {
    sourcePending = true
    vi.mocked(window.confirm).mockReturnValue(false)
    renderPage()
    expect(await screen.findByText('报告来源待快速复核')).toBeTruthy()
    const button = await screen.findByRole('button', { name: /立即开始压缩/ })
    fireEvent.click(button)
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/请勿修改、移动或删除源文件/))
  }, 15000)

  it('allows and persists a disc-number edit before compression, then posts one archive decision with the new shell revision', async () => {
    renderPage(); await editDiscAndClick()
    await waitFor(() => expect(decisionBodies).toHaveLength(1))
    expect(events.indexOf('draft-save')).toBeGreaterThanOrEqual(0)
    expect(events.indexOf('draft-save')).toBeLessThan(events.indexOf('archive-decision'))
    const savedDraft = (patchMock.mock.calls[0][1] as { draft: CaseDraft }).draft
    expect(savedDraft.report.attachments.disc_number).toBe('GP20260731-002')
    expect(decisionBodies[0].expected_revision).toBe(6)
    expect(patchMock).toHaveBeenCalledTimes(1)
    expect(postMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_ARCHIVE_DECISION(caseId))).toHaveLength(1)
  }, 15000)

  it('does not save or create an archive task when the direct-source warning is cancelled', async () => {
    vi.mocked(window.confirm).mockReturnValue(false)
    renderPage()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: /立即开始压缩/ }))
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/请勿修改、移动或删除源文件/))
    expect(patchMock).not.toHaveBeenCalled()
    expect(decisionBodies).toHaveLength(0)
  }, 15000)

  it.each([
    ['archive_deferred', /开始压缩/],
    ['archive_interrupted', /重新确认并立即压缩/],
  ] as const)('requires direct-source confirmation from %s before creating a task', async (lifecycle, buttonName) => {
    initialLifecycle = lifecycle
    vi.mocked(window.confirm).mockReturnValue(false)
    renderPage()
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    fireEvent.click(await screen.findByRole('button', { name: buttonName }))
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/请勿修改、移动或删除源文件/))
    expect(decisionBodies).toHaveLength(0)

    vi.mocked(window.confirm).mockReturnValue(true)
    fireEvent.click(screen.getByRole('button', { name: buttonName }))
    await waitFor(() => expect(decisionBodies).toHaveLength(1))
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

  it('saves a newly selected inspector once without entering a PATCH loop', async () => {
    renderPage()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_LEASE(caseId), expect.anything()))
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())

    fireEvent.click(screen.getByRole('button', { name: '添加检查人员' }))
    fireEvent.click(await screen.findByRole('button', { name: '添加张三' }))

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1), { timeout: 5000 })
    await new Promise(resolve => setTimeout(resolve, 1200))
    expect(patchMock).toHaveBeenCalledTimes(1)
  }, 15000)

  it('keeps the top disc-number input editable and autosaved while compression is running', async () => {
    initialLifecycle = 'archive_queued'
    renderPage()
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    expect(await screen.findByText('压缩正在后台进行；现在仍可填写首个光盘编号，压缩完成后将沿用该编号。')).toBeTruthy()
    fireEvent.change(screen.getByRole('textbox', { name: '首个光盘编号' }), { target: { value: 'GP20260731-009' } })
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1), { timeout: 5000 })
    const savedDraft = (patchMock.mock.calls[0][1] as { draft: CaseDraft }).draft
    expect(savedDraft.report.attachments.disc_number).toBe('GP20260731-009')
  }, 15000)

  it('shows completed archive parts and their disc mapping in the attachments section', async () => {
    showCompletedArchive = true
    renderPage()
    expect(await screen.findByText('合成案件.part1.rar')).toBeTruthy()
    expect(screen.getByText('合成案件.part2.rar')).toBeTruthy()
    expect(screen.getByText('GP20260731-01')).toBeTruthy()
    expect(screen.getByText('GP20260731-02')).toBeTruthy()
    expect((screen.getByRole('textbox', { name: '首个光盘编号' }) as HTMLInputElement).value).toBe('GP20260731-01')
    expect(screen.getByRole('button', { name: '更新盘号映射' })).toBeTruthy()
    expect(getMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT(archiveTaskSummary.task_id), { timeout: WORKBENCH_REQUEST_TIMEOUT_MS })
  }, 15000)

  it('collects a first disc number after compression and posts the disc mapping', async () => {
    archiveResultParts = completedArchiveResult.parts.map(part => ({ ...part, disc_number: '', disc_date: '' }))
    try {
      showCompletedArchive = true
      renderPage()
      expect(await screen.findByText('待补盘号')).toBeTruthy()
      fireEvent.change(await screen.findByPlaceholderText('如 GP20260731-01'), { target: { value: 'GP20260731-01' } })
      fireEvent.click(screen.getByRole('button', { name: /提交盘号映射/ }))
      await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_ARCHIVE_DISC_MAPPING(caseId), { expected_revision: 5, expected_plan_row_revision: 4, first_disc_number: 'GP20260731-01' }, { timeout: WORKBENCH_REQUEST_TIMEOUT_MS }))
      await waitFor(() => expect(screen.getByText('归档完成')).toBeTruthy())
      expect((screen.getByRole('textbox', { name: '首个光盘编号' }) as HTMLInputElement).value).toBe('GP20260731-01')
      expect(screen.getByText('GP20260731-02')).toBeTruthy()
      expect(getMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT(archiveTaskSummary.task_id))).toHaveLength(2)
    } finally {
      archiveResultParts = null
    }
  }, 15000)

  it('blocks browser and SPA navigation until recovered photo bindings finish saving', async () => {
    recoverPhotoOnLoad = true
    holdSave = true
    const view = renderPage()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))

    await act(async () => { void view.router.navigate(-1) })
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(screen.queryByText('工作台路由')).toBeNull()

    holdSave = false
    await act(async () => { resolveSave?.() })
    resolveSave = null
    await screen.findByText('工作台路由')
  }, 15000)

  it('asks for a Word file name then picks a fresh directory and triggers the unified export bundle', async () => {
    showCompletedArchive = true
    archiveResultParts = completedArchiveResult.parts.map((part, index) => ({
      ...part,
      size_bytes: index === 0 ? 22_000_000_000 : 23_000_000_000,
    }))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /开始导出/ }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Word 下载文件名'), { target: { value: '合成案件.docx' } })
    fireEvent.click(within(dialog).getByRole('button', { name: '开始导出' }))
    // Fresh grant on every export — re-export must not reuse a consumed token (422 regression).
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY, undefined, expect.anything()))
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_UNIFIED_EXPORT(caseId), { expected_revision: 5, export_path: 'D:\\SYNTHETIC\\EXPORT', directory_token: 'token-synthetic', word_filename: '合成案件.docx' }, { timeout: unifiedExportRequestTimeoutMs(45_000_000_000) }))
  }, 15000)

  it('shows the exported state for a re-exported case', async () => {
    useExportedLifecycle = true
    renderPage()
    expect(await screen.findByRole('button', { name: /再次导出/ })).toBeTruthy()
    expect(screen.getByText('已导出')).toBeTruthy()
  }, 15000)
})
