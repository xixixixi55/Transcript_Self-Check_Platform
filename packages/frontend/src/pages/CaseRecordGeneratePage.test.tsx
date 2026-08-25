import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import axios from 'axios'
import { API_ENDPOINTS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import { unifiedExportRequestTimeoutMs } from '@biji/shared/utils'
import type { ArchiveTaskResult, CaseDraft, CaseShell } from '@biji/shared/types'
import CaseRecordGeneratePage from './CaseRecordGeneratePage'
import { archiveTaskSummary, availableInspector, caseId, completedArchiveResult, defaults, detail, identity, lease, report, reportWithPhotos, task } from './CaseRecordGeneratePage.test-fixtures'
vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() } }))
const getMock = vi.mocked(axios.get); const postMock = vi.mocked(axios.post); const patchMock = vi.mocked(axios.patch)

describe('CaseRecordGeneratePage archive decision coordination', () => {
  let detailReads = 0
  let decisionBodies: Record<string, unknown>[] = []
  let events: string[] = []
  let rejectSave = false, failSharedDefaults = false, conflictDecision = false, holdSave = false, holdDirectory = false
  let showCompletedArchive = false, useExportedLifecycle = false, sourcePending = false, recoverPhotoOnLoad = false, failPhotoAssetRead = false, unextractableWithoutReason = false
  let initialLifecycle: CaseShell['lifecycle'] = 'review_ready'
  let resolveSave: (() => void) | null = null, resolveDirectory: (() => void) | null = null
  let archiveResultParts: ArchiveTaskResult['parts'] | null = null
  beforeAll(() => { Object.defineProperty(window, 'matchMedia', { writable: true, value: () => ({ matches: false, media: '', onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() }) }) })
  beforeEach(() => {
    vi.clearAllMocks(); detailReads = 0; decisionBodies = []; events = []; rejectSave = false; failSharedDefaults = false; conflictDecision = false; holdSave = false; holdDirectory = false; showCompletedArchive = false; useExportedLifecycle = false; sourcePending = false; recoverPhotoOnLoad = false; failPhotoAssetRead = false; unextractableWithoutReason = false; initialLifecycle = 'review_ready'; resolveSave = null; resolveDirectory = null; archiveResultParts = null
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
        if (unextractableWithoutReason && value.draft) {
          value.draft.report.introduction.evidence_list = [{
            id: 'material-unextractable', device_type: 'SYNTHETIC HUAWEI ADY-AL10',
            evidence_number: 'SYN-E-REASON', material_type: 'phone',
            material_type_status: 'confirmed_by_user', material_type_source: 'user',
            extractable: false, unextractable_reason: '',
          }]
        }
        return { data: { data: value } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_TASK(task.task_id)) return { data: { data: task } }
      if (url === API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT(archiveTaskSummary.task_id)) {
        return { data: { data: { ...completedArchiveResult, parts: archiveResultParts ?? completedArchiveResult.parts } } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_CASE_ASSETS(caseId)) return { data: { data: { items: recoverPhotoOnLoad ? [{ asset_id: 'asset-synthetic-recovered', asset_kind: 'image', fingerprint: 'a'.repeat(64), metadata: { file_name: 'SYNTHETIC-recovered.png', extension: '.png', media_type: 'image/png', size_bytes: 1 }, content_status: 'available' }] : [] } } }
      if (url === API_ENDPOINTS.WORKBENCH_CASE_ASSET(caseId, 'asset-synthetic-recovered')) return failPhotoAssetRead ? Promise.reject(new Error('SYNTHETIC_PHOTO_READ_FAILED')) : { data: new Blob(['SYNTHETIC-PHOTO'], { type: 'image/png' }) }
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
      if (url === API_ENDPOINTS.EXPORT_RECORD) {
        const form = body as FormData
        return form.get('export_path')
          ? { data: { data: { export_path: form.get('export_path'), word_filename: form.get('word_filename') } } }
          : { data: new Blob(['SYNTHETIC-DOCX']) }
      }
      if (url === API_ENDPOINTS.WORKBENCH_ARCHIVE_DISC_MAPPING(caseId)) {
        const request = body as { expected_revision: number; expected_plan_row_revision: number; first_disc_number: string }
        archiveResultParts = completedArchiveResult.parts.map((part, index) => ({
          ...part,
          disc_number: index === 0 ? request.first_disc_number : 'GP2026073102-02',
          disc_date: '2026-07-31',
        }))
        return { data: { data: { case_id: caseId, task_id: 'archive-synthetic-1', expected_revision: request.expected_revision, plan_row_revision: request.expected_plan_row_revision + 1, lifecycle: 'archive_verified', prefix: 'GP', disc_date: '2026-07-31', parts: archiveResultParts.map((part, index) => ({ part_number: index + 1, disc_number: part.disc_number, disc_date: part.disc_date })) } } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY) { if (holdDirectory) await new Promise<void>(resolve => { resolveDirectory = resolve }); return { data: { data: { path: 'D:\\SYNTHETIC\\EXPORT', token: 'token-synthetic' } } } }
      if (url === API_ENDPOINTS.WORKBENCH_UNIFIED_EXPORT(caseId)) {
        const request = body as { expected_revision: number; export_path: string; directory_token: string }
        return { data: { data: { case_id: caseId, task_id: 'archive-synthetic-1', expected_revision: request.expected_revision, lifecycle: 'exported', output: { export_path: request.export_path, word_filename: 'SYNTHETIC.docx', rar_filenames: ['SYNTHETIC.part1.rar'], exported_at: '2026-01-01T00:00:00Z' } } } }
      }
      return { data: { data: {} } }
    })
    patchMock.mockImplementation(async (url: string, body: unknown) => {
      if (url === API_ENDPOINTS.WORKBENCH_CASE_PHOTO_BINDING(caseId)) {
        const request = body as { asset_refs: CaseDraft['asset_refs'] }
        const latest = detail(7, 7, initialLifecycle).draft!
        const bindingResponse = { data: { data: { draft: {
          ...latest, asset_refs: request.asset_refs,
          report: reportWithPhotos(latest.report, request.asset_refs.map(item => item.asset_id)),
          revision: 8,
        } } } }
        if (holdSave) return new Promise(resolve => { resolveSave = () => resolve(bindingResponse) })
        return bindingResponse
      }
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

  it('defaults to the guided shell and mounts the full editor only on demand without losing draft state', async () => {
    renderPage()
    const historyRegion = await screen.findByRole('region', { name: '历史处理轨迹' })
    const conversationRegion = screen.getByRole('region', { name: '当前对话' })
    expect(historyRegion.compareDocumentPosition(conversationRegion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(document.querySelector('.review-editor-form')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '完整审核编辑' }))
    await waitFor(() => expect(document.querySelector('.review-editor-form')).toBeTruthy())
    const discInput = screen.getByRole('textbox', { name: '介质编号' })
    fireEvent.change(discInput, { target: { value: 'GP20260731-009' } })

    fireEvent.click(screen.getByRole('button', { name: '返回引导模式' }))
    await screen.findByRole('region', { name: '当前对话' })
    expect(document.querySelector('.review-editor-form')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '完整审核编辑' }))
    expect((await screen.findByRole('textbox', { name: '介质编号' }) as HTMLInputElement).value).toBe('GP20260731-009')
    expect(postMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_LEASE(caseId))).toHaveLength(1)
  }, 15000)

  async function openFullEditor() {
    const button = await screen.findByRole('button', { name: '完整审核编辑' })
    fireEvent.click(button)
    await waitFor(() => expect(document.querySelector('.review-editor-form')).toBeTruthy())
  }

  async function editDiscNumber() {
    await openFullEditor()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_LEASE(caseId), expect.anything()))
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    const input = await screen.findByRole('textbox', { name: '介质编号' })
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
    await openFullEditor()
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
    await openFullEditor()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: /立即开始压缩/ }))
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/请勿修改、移动或删除源文件/))
    expect(patchMock).not.toHaveBeenCalled()
    expect(decisionBodies).toHaveLength(0)
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

  it('locks editing before flushing an immediate edit for Word export', async () => {
    failSharedDefaults = true; holdSave = true
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    try {
      renderPage()
      await editDiscNumber()
      fireEvent.click(screen.getByRole('button', { name: /导出 Word/ }))
      fireEvent.click(await screen.findByRole('button', { name: '开始导出' }))
      await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1)); expect((document.querySelector('.review-editor-form__fieldset') as HTMLFieldSetElement).disabled).toBe(true)
      expect(postMock.mock.calls.some(([url]) => url === API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY)).toBe(false)
      holdSave = false; resolveSave?.(); resolveSave = null
      await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY, undefined, expect.anything()))
      await waitFor(() => expect(postMock.mock.calls.some(([url]) => url === API_ENDPOINTS.EXPORT_RECORD)).toBe(true))
      const formData = postMock.mock.calls.find(([url]) => url === API_ENDPOINTS.EXPORT_RECORD)?.[1] as FormData
      expect(formData.get('case_id')).toBe(caseId); expect(formData.get('case_revision')).toBe('6')
      expect(formData.get('export_path')).toBe('D:\\SYNTHETIC\\EXPORT'); expect(formData.get('directory_token')).toBe('token-synthetic')
      expect(events.indexOf('draft-save')).toBeLessThan(postMock.mock.calls.findIndex(([url]) => url === API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY))
    } finally {
      anchorClick.mockRestore()
    }
  }, 15000)

  it('blocks Word export until every unextractable material has a reason', async () => {
    unextractableWithoutReason = true
    renderPage()
    await openFullEditor()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())

    fireEvent.click(screen.getByRole('button', { name: /导出 Word/ }))

    expect(screen.queryByRole('button', { name: '开始导出' })).toBeNull()
    expect(postMock.mock.calls.some(([url]) => url === API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY)).toBe(false)
  }, 15000)

  it('uses the latest revision when photo binding finishes during directory selection after timeout', async () => {
    recoverPhotoOnLoad = true; failPhotoAssetRead = true; holdSave = true; holdDirectory = true; renderPage()
    await openFullEditor()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 }); await waitFor(() => expect(patchMock.mock.calls.some(([url]) => url === API_ENDPOINTS.WORKBENCH_CASE_PHOTO_BINDING(caseId))).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: /导出 Word/ })); fireEvent.click(await screen.findByRole('button', { name: '开始导出' }))
    await waitFor(() => expect(postMock.mock.calls.some(([url]) => url === API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY)).toBe(true), { timeout: 7000 }); await act(async () => { holdSave = false; resolveSave?.(); resolveSave = null; await Promise.resolve() }); holdDirectory = false; resolveDirectory?.(); resolveDirectory = null
    await waitFor(() => expect(postMock.mock.calls.some(([url]) => url === API_ENDPOINTS.EXPORT_RECORD)).toBe(true)); const formData = postMock.mock.calls.find(([url]) => url === API_ENDPOINTS.EXPORT_RECORD)?.[1] as FormData
    expect(formData.getAll('photos')).toHaveLength(0); expect(formData.get('case_revision')).toBe('8')
  }, 15000)

  it('saves a newly selected inspector once without entering a PATCH loop', async () => {
    renderPage()
    await openFullEditor()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_LEASE(caseId), expect.anything()))
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())

    fireEvent.click(screen.getByRole('button', { name: '添加检查人员' }))
    fireEvent.click(await screen.findByRole('button', { name: '添加张三' }))
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1), { timeout: 5000 })
    await new Promise(resolve => setTimeout(resolve, 1200))
    expect(patchMock).toHaveBeenCalledTimes(1)
  }, 15000)
  it('saves an explicitly cleared entrust-unit prefix only to the current draft', async () => {
    renderPage()
    await openFullEditor()
    await screen.findByRole('heading', { name: '审核编辑', level: 2 })
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    fireEvent.click(screen.getByText('SYNTHETIC-PREFIX'))
    const input = screen.getByDisplayValue('SYNTHETIC-PREFIX')
    fireEvent.change(input, { target: { value: '' } })
    fireEvent.blur(input)

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1), { timeout: 5000 })
    const request = patchMock.mock.calls[0][1] as {
      draft: CaseDraft
      shared_defaults_patch?: Record<string, unknown> | null
    }
    expect(request.draft.report.introduction.entrust_unit_prefix).toBe('')
    expect(request.draft.report.introduction.entrust_unit).toBe('SYNTHETIC-UNIT')
    expect(request.shared_defaults_patch).toBeNull()
  }, 15000)

  it.each(['archive_queued', 'archive_deferred'] as const)('accepts and autosaves a YP number without medium guidance while lifecycle is %s', async lifecycle => {
    initialLifecycle = lifecycle
    renderPage()
    await openFullEditor()
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    expect(screen.queryByText(/压缩正在后台进行，可以先填写编号/)).toBeNull()
    expect(screen.queryByText(/最终介质由压缩前归档总量决定，可以先填写编号/)).toBeNull()
    expect(screen.queryByText('GPyyyyMMddXX-序号 · 光盘')).toBeNull()
    expect(screen.queryByText('YPyyyyMMddXX-序号 · 硬盘')).toBeNull()
    fireEvent.change(screen.getByRole('textbox', { name: '介质编号' }), { target: { value: 'YP2026073102-009' } })
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1), { timeout: 5000 })
    const savedDraft = (patchMock.mock.calls[0][1] as { draft: CaseDraft }).draft
    expect(savedDraft.report.attachments.disc_number).toBe('YP2026073102-009')
  }, 15000)

  it('collects a first disc number after compression and posts the disc mapping', async () => {
    archiveResultParts = completedArchiveResult.parts.map(part => ({ ...part, disc_number: '', disc_date: '' }))
    try {
      showCompletedArchive = true
      renderPage()
      await openFullEditor()
      expect(await screen.findByText('待补盘号')).toBeTruthy()
      fireEvent.change(await screen.findByPlaceholderText('如 GP2026073102-01'), { target: { value: 'GP2026073102-01' } })
      fireEvent.click(screen.getByRole('button', { name: /提交盘号映射/ }))
      await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_ARCHIVE_DISC_MAPPING(caseId), { expected_revision: 5, expected_plan_row_revision: 4, first_disc_number: 'GP2026073102-01' }, { timeout: WORKBENCH_REQUEST_TIMEOUT_MS }))
      await waitFor(() => expect(screen.getByText('归档完成')).toBeTruthy())
      expect((screen.getByRole('textbox', { name: '首个光盘编号' }) as HTMLInputElement).value).toBe('GP2026073102-01')
      expect(screen.getByText('GP2026073102-02')).toBeTruthy()
      expect(getMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT(archiveTaskSummary.task_id))).toHaveLength(2)
    } finally {
      archiveResultParts = null
    }
  }, 15000)

  it('blocks browser and SPA navigation until recovered photo bindings finish saving', async () => {
    recoverPhotoOnLoad = true
    holdSave = true
    const view = renderPage()
    await openFullEditor()
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
    await openFullEditor()
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
    await openFullEditor()
    expect(await screen.findByRole('button', { name: /再次导出/ })).toBeTruthy()
    expect(screen.getByText('已导出')).toBeTruthy()
  }, 15000)
})
