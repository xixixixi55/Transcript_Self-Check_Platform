import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import axios from 'axios'
import { API_ENDPOINTS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import type { ArchiveTaskResult, CaseDraft, CaseShell } from '@biji/shared/types'
import CaseRecordGeneratePage from './CaseRecordGeneratePage'
import { archiveTaskSummary, availableInspector, caseId, completedArchiveResult, defaults, detail, identity, lease, report, reportWithPhotos, task } from './CaseRecordGeneratePage.test-fixtures'
vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() } }))
const getMock = vi.mocked(axios.get); const postMock = vi.mocked(axios.post); const patchMock = vi.mocked(axios.patch)

describe('CaseRecordGeneratePage archive decision coordination', () => {
  let detailReads = 0
  let decisionBodies: Record<string, unknown>[] = []
  let events: string[] = []
  let rejectSave = false, conflictSave = false, failSharedDefaults = false, conflictDecision = false, holdSave = false, holdDirectory = false
  let leaseFailure = false, leaseConflict = false
  let showCompletedArchive = false, showGuidedReady = false, showManualReviewComplete = false, showDeferredTerminal = false, showPhotoPending = false, showHandledHistory = false, showHandledCompleteness = false, showHandledCaseSummary = false, showHandledDiscNumber = false, useExportedLifecycle = false, sourcePending = false, recoverPhotoOnLoad = false, failPhotoAssetList = false, failPhotoAssetRead = false, unextractableWithoutReason = false, emptyInspectors = false
  let caseSummaryConfirmationSaved = false
  let initialLifecycle: CaseShell['lifecycle'] = 'review_ready'
  let resolveSave: (() => void) | null = null, resolveDirectory: (() => void) | null = null
  let archiveResultParts: ArchiveTaskResult['parts'] | null = null
  let persistedCaseRevision = 5, archivePlanRowRevision = 4
  beforeAll(() => {
    Object.defineProperty(window, 'matchMedia', { writable: true, value: () => ({ matches: false, media: '', onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() }) })
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
  })
  beforeEach(() => {
    window.localStorage.clear()
    vi.clearAllMocks(); detailReads = 0; decisionBodies = []; events = []; rejectSave = false; conflictSave = false; failSharedDefaults = false; conflictDecision = false; holdSave = false; holdDirectory = false; leaseFailure = false; leaseConflict = false; showCompletedArchive = false; showGuidedReady = false; showManualReviewComplete = false; showDeferredTerminal = false; showPhotoPending = false; showHandledHistory = false; showHandledCompleteness = false; showHandledCaseSummary = false; showHandledDiscNumber = false; caseSummaryConfirmationSaved = false; useExportedLifecycle = false; sourcePending = false; recoverPhotoOnLoad = false; failPhotoAssetList = false; failPhotoAssetRead = false; unextractableWithoutReason = false; emptyInspectors = false; initialLifecycle = 'review_ready'; resolveSave = null; resolveDirectory = null; archiveResultParts = null; persistedCaseRevision = 5; archivePlanRowRevision = 4
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getMock.mockImplementation(async (url: string) => {
      if (url === API_ENDPOINTS.WORKBENCH_DEFAULTS) return { data: { data: defaults } }
      if (url === API_ENDPOINTS.WORKBENCH_CASE(caseId)) {
        const read = detailReads++
        const value = useExportedLifecycle ? detail(5, 5, 'exported', 'GP20260731-001', archiveTaskSummary)
          : showManualReviewComplete ? detail(5, 5, 'archiving', 'GP20260731-001', {
            ...archiveTaskSummary, status: 'running', stage: 'winrar', stage_label: '正在生成压缩分卷', finished_at: null,
          })
            : showCompletedArchive || showGuidedReady ? detail(5, 5, 'archive_verified', 'GP20260731-001', archiveTaskSummary)
              : showDeferredTerminal ? detail(5, 5, 'archive_deferred')
                : initialLifecycle !== 'review_ready' ? detail(5, 5, initialLifecycle)
                  : read === 0 ? detail(5, 5)
                    : read === 1 ? detail(6, 6, 'review_ready', 'GP20260731-002')
                      : detail(7, 6, 'archive_queued', 'GP20260731-002')
        if ((showGuidedReady || showManualReviewComplete || showDeferredTerminal) && value.draft) {
          value.draft.field_states = { 'introduction.evidence_list.completeness': {
            field_path: 'introduction.evidence_list.completeness', source: 'user', confirmation: 'confirmed',
            revision: 1, last_changed_at: '2026-01-01T00:00:00Z',
          } }
          value.draft.report.introduction.evidence_list = [{
            id: 'material-synthetic-ready', device_type: 'SYNTHETIC Phone', evidence_number: 'SYN-JC00000001',
            material_type: 'phone', material_type_status: 'confirmed_by_report', material_type_source: 'report',
            extractable: true, imei1: '000000000000001',
          }]
          value.draft.report.attachments.photo_ids = ['asset-synthetic-ready-front', 'asset-synthetic-ready-back']
          value.draft.report.inspection.primary_software = {
            name: 'SYNTHETIC-TOOL', version: '1.0', display_name: 'SYNTHETIC-TOOL 1.0',
            confirmation_status: 'confirmed_by_report', provenance: [], candidates: [],
          }
          Object.assign(value.draft.report.inspection.result, {
            rar_filename: 'SYNTHETIC.rar', md5_hash: 'a'.repeat(32), file_size: '1 KB',
          })
        }
        if (showPhotoPending && value.draft) {
          value.draft.report.introduction.evidence_list = [{
            id: 'material-synthetic-photo', device_type: 'SYNTHETIC Phone',
            evidence_number: 'SYN-JC00000002', material_type: 'phone',
            material_type_status: 'confirmed_by_report', material_type_source: 'report',
            extractable: true, imei1: '000000000000002',
          }]
          value.draft.report.attachments.photo_ids = []
        }
        if (showHandledHistory && value.draft) {
          value.draft.field_states = {
            ...value.draft.field_states,
            document_number: {
              field_path: 'document_number', source: 'user', confirmation: 'confirmed',
              revision: 1, last_changed_at: '2026-01-01T00:00:00Z',
            },
          }
        }
        if (showHandledCompleteness && value.draft) {
          value.draft.field_states = {
            ...value.draft.field_states,
            'introduction.evidence_list.completeness': {
              field_path: 'introduction.evidence_list.completeness', source: 'user', confirmation: 'confirmed',
              revision: 1, last_changed_at: '2026-01-01T00:00:00Z',
            },
          }
        }
        if ((showHandledCaseSummary || caseSummaryConfirmationSaved) && value.draft) {
          value.draft.field_states = {
            ...value.draft.field_states,
            'introduction.case_summary.confirmation': {
              field_path: 'introduction.case_summary.confirmation', source: 'user', confirmation: 'confirmed',
              revision: 1, last_changed_at: '2026-09-03T00:00:00Z',
            },
          }
        }
        if (showHandledDiscNumber && value.draft) {
          value.draft.field_states = {
            ...value.draft.field_states,
            'attachments.disc_number': {
              field_path: 'attachments.disc_number', source: 'user', confirmation: 'confirmed',
              revision: 1, last_changed_at: '2026-09-10T00:00:00Z',
            },
          }
        }
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
        if (emptyInspectors && value.draft) value.draft.report.introduction.inspectors = []
        return { data: { data: value } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_TASK(task.task_id)) return { data: { data: task } }
      if (url === API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT(archiveTaskSummary.task_id)) {
        return { data: { data: { ...completedArchiveResult, plan_row_revision: archivePlanRowRevision, parts: archiveResultParts ?? completedArchiveResult.parts } } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_CASE_ASSETS(caseId)) {
        if (failPhotoAssetList) throw { response: { data: { detail: { code: 'PHOTO_BINDING_CONFLICT' } } } }
        return { data: { data: { items: recoverPhotoOnLoad ? [{ asset_id: 'asset-synthetic-recovered', asset_kind: 'image', fingerprint: 'a'.repeat(64), metadata: { file_name: 'SYNTHETIC-recovered.png', extension: '.png', media_type: 'image/png', size_bytes: 1 }, content_status: 'available' }] : [] } } }
      }
      if (url === API_ENDPOINTS.WORKBENCH_CASE_ASSET(caseId, 'asset-synthetic-recovered')) return failPhotoAssetRead ? Promise.reject(new Error('SYNTHETIC_PHOTO_READ_FAILED')) : { data: new Blob(['SYNTHETIC-PHOTO'], { type: 'image/png' }) }
      if (url === API_ENDPOINTS.DEVICES) return { data: { data: [] } }
      if (url === API_ENDPOINTS.INSPECTORS) return { data: { data: [availableInspector] } }
      throw new Error(`unexpected GET ${url}`)
    })
    postMock.mockImplementation(async (url: string, body?: unknown) => {
      if (url === API_ENDPOINTS.WORKBENCH_LEASE(caseId)) {
        if (leaseConflict) throw { response: { data: { detail: { code: 'LEASE_CONFLICT' } } } }
        if (leaseFailure) throw { response: { data: { detail: { code: 'LEASE_REQUEST_FAILED' } } } }
        return { data: { data: lease } }
      }
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
        if (request.expected_revision !== persistedCaseRevision
          || request.expected_plan_row_revision !== archivePlanRowRevision) {
          throw { response: { status: 409, data: { detail: { code: 'REVISION_CONFLICT', message: '案件或归档计划已被修改。' } } } }
        }
        archivePlanRowRevision += 1
        archiveResultParts = completedArchiveResult.parts.map((part, index) => ({
          ...part,
          disc_number: index === 0 ? request.first_disc_number : 'GP2026073102-02',
          disc_date: '2026-07-31',
        }))
        return { data: { data: { case_id: caseId, task_id: 'archive-synthetic-1', expected_revision: request.expected_revision, plan_row_revision: request.expected_plan_row_revision + 1, lifecycle: 'archive_verified', prefix: 'GP', disc_date: '2026-07-31', parts: archiveResultParts.map((part, index) => ({ part_number: index + 1, disc_number: part.disc_number, disc_date: part.disc_date })) } } }
      }
      if (url.endsWith('/export-directory')) { if (holdDirectory) await new Promise<void>(resolve => { resolveDirectory = resolve }); return { data: { data: { path: 'D:\\SYNTHETIC\\EXPORT', token: 'token-synthetic' } } } }
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
      if (conflictSave) throw {
        response: { status: 409, data: { detail: { code: 'REVISION_CONFLICT', data: {
          draft_save_status: { status: 'conflict', error_code: 'REVISION_CONFLICT' },
          shared_defaults_save_status: { status: 'failed', error_code: 'DRAFT_SAVE_NOT_APPLIED' },
        } } } },
      }
      const request = body as { draft: CaseDraft; shared_defaults_patch?: Record<string, unknown> | null }
      persistedCaseRevision = 6
      caseSummaryConfirmationSaved = request.draft.field_states['introduction.case_summary.confirmation']?.confirmation === 'confirmed'
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

  it('uses the guided assistant as the only review interface', async () => {
    renderPage()
    const historyRegion = await screen.findByRole('region', { name: 'Word 内容预览' })
    const conversationRegion = screen.getByRole('region', { name: '当前对话' })
    expect(historyRegion.compareDocumentPosition(conversationRegion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(document.querySelector('.review-editor-form')).toBeNull()
    expect(screen.queryByText('笔录生成 / 审核编辑')).toBeNull()
    expect(screen.queryByRole('button', { name: '打开结构摘要预览' })).toBeNull()
    expect(screen.getByRole('button', { name: '返回案件工作台' }).querySelector('.anticon-home')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /完整审核|返回引导模式|导出 Word/ })).toBeNull()
    expect(postMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_LEASE(caseId))).toHaveLength(1)
  }, 15000)

  it('speaks the archive decision prompt while the reply presents only the choices', async () => {
    renderPage()

    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('请选择压缩时机'))
    const assistantMessage = screen.getByRole('status', { name: '獬豸助手提示' })
    const reply = screen.getByRole('group', { name: '请选择操作' })
    expect(assistantMessage.textContent).toContain('建议现在开始压缩；也可以保留案件并稍后处理。')
    expect(within(reply).queryByText('报告解析成功，请选择压缩时机。')).toBeNull()
    expect(within(reply).getByRole('button', { name: '立即开始压缩' })).toBeTruthy()
    expect(within(reply).getByRole('button', { name: '稍后压缩' })).toBeTruthy()
  }, 15000)

  it('reopens the matching guided assistant field from a previously handled item', async () => {
    showHandledHistory = true
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: /查看已填内容与待办/ }))
    const panel = await screen.findByRole('region', { name: '已填内容与待办' })
    fireEvent.click(within(panel).getByRole('button', { name: '修改文号' }))

    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('请输入文号'))
    expect(screen.getByRole('textbox', { name: '文号' })).toBeTruthy()
    expect(document.querySelector('.review-editor-form')).toBeNull()
  }, 15000)

  it('edits evidence in the Word preview and sends it through draft autosave', async () => {
    showGuidedReady = true; renderPage()
    const historyRegion = await screen.findByRole('region', { name: 'Word 内容预览' })
    expect(within(historyRegion).queryByRole('button', { name: /修改检材 1/ })).toBeNull()
    fireEvent.click(await within(historyRegion).findByRole('button', { name: /SYNTHETIC Phone，按 Enter 编辑/ }))
    const deviceInput = within(historyRegion).getByDisplayValue('SYNTHETIC Phone'); fireEvent.change(deviceInput, { target: { value: 'SYNTHETIC Updated Phone' } }); fireEvent.blur(deviceInput)
    await waitFor(() => expect(patchMock.mock.calls.some(([url, body]) => url === API_ENDPOINTS.WORKBENCH_DRAFT(caseId)
      && (body as { draft: CaseDraft }).draft.report.introduction.evidence_list[0]?.device_name === 'SYNTHETIC Updated Phone')).toBe(true))
    expect(within(historyRegion).getByText('已自动保存')).toBeTruthy()

    fireEvent.click(await within(historyRegion).findByRole('button', { name: '未填写，按 Enter 编辑' }))
    const holderField = within(historyRegion).getByText('持有人：').closest('.guided-review-history__field')
    expect(holderField).toBeTruthy()
    const holderInput = within(holderField as HTMLElement).getByRole('textbox')
    fireEvent.change(holderInput, { target: { value: 'SYNTHETIC-HOLDER-A' } })
    fireEvent.blur(holderInput)
    await waitFor(() => expect(patchMock.mock.calls.some(([url, body]) => url === API_ENDPOINTS.WORKBENCH_DRAFT(caseId)
      && (body as { draft: CaseDraft }).draft.report.introduction.evidence_list[0]?.holder_name === 'SYNTHETIC-HOLDER-A')).toBe(true))
  }, 15000)
  it('restores confirmed evidence completeness under previously handled after reopening the case', async () => {
    showHandledCompleteness = true
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: /查看已填内容与待办/ }))
    const panel = await screen.findByRole('region', { name: '已填内容与待办' })
    const completenessButton = within(panel).getByRole('button', { name: '修改检材完整性' })
    expect(completenessButton.textContent).toContain('已确认')
    fireEvent.click(completenessButton)

    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('请确认检材完整性'))
    expect(screen.queryByRole('button', { name: '确认检材信息完整' })).toBeNull()
    expect(screen.getByRole('button', { name: '进入下一步' })).toBeTruthy()
  }, 15000)

  it('reopens evidence completeness instead of keeping save and exit visible after review completion', async () => {
    showGuidedReady = true
    showHandledCompleteness = true
    showHandledCaseSummary = true
    renderPage()

    expect(await screen.findByRole('button', { name: /保存并退出/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /查看已填内容与待办/ })).toBeNull()
    fireEvent.click(await screen.findByRole('button', { name: '返回上一步' }))
    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('请核对检材照片'))
    fireEvent.click(screen.getByRole('button', { name: '返回上一步' }))

    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('请确认检材完整性'))
    expect(screen.queryByRole('button', { name: '确认检材信息完整' })).toBeNull()
    expect(screen.getByRole('button', { name: '进入下一步' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /保存并退出/ })).toBeNull()
  }, 15000)

  it('restores a confirmed case summary under previously handled after reopening the case', async () => {
    showHandledCaseSummary = true
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: /查看已填内容与待办/ }))
    const panel = await screen.findByRole('region', { name: '已填内容与待办' })
    fireEvent.click(within(panel).getByRole('button', { name: '修改案件简要情况' }))

    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('请输入案件简要情况'))
    expect(screen.getByRole('textbox', { name: '案件简要情况' })).toBeTruthy()
    expect(document.querySelector('.review-editor-form')).toBeNull()
  }, 15000)

  it('keeps the guided conversation open with only quick batch evidence supplementation', async () => {
    renderPage()

    await selectGuidedAction('请确认检材完整性')
    const incompleteButton = await screen.findByRole('button', { name: '检材信息不完整，手工添加检材' })
    expect(incompleteButton.querySelector('.anticon-file-add')).toBeTruthy()
    fireEvent.click(incompleteButton)
    expect(screen.queryByRole('button', { name: /逐项编辑/ })).toBeNull()

    expect(screen.getByRole('region', { name: '当前对话' })).toBeTruthy()
    expect(document.querySelector('.review-editor-form')).toBeNull()
    expect(screen.getByRole('textbox', { name: '快捷批量添加检材' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '快捷批量补充检材' })).toBeNull()
    expect(screen.queryByRole('button', { name: /逐项编辑/ })).toBeNull()
  }, 15000)

  it('keeps one usable photo page when photo binding needs recovery', async () => {
    showPhotoPending = true; failPhotoAssetList = true
    renderPage()

    await selectGuidedAction('请上传检材照片')
    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('图片列表已被另一会话修改，请重新读取案件后再保存。'))
    const assistantMessage = screen.getByRole('status', { name: '獬豸助手提示' })
    const reply = screen.getByRole('group', { name: '你的回复' })
    expect(assistantMessage.textContent).toContain('每个检材对应两张图片；支持普通数字自然排序，或用 1-1、1-2 表示第一个检材的两张图片。')
    expect(within(reply).queryByText('图片列表已被另一会话修改，请重新读取案件后再保存。')).toBeNull()
    expect(within(reply).queryByText('每个检材对应两张图片；支持普通数字自然排序，或用 1-1、1-2 表示第一个检材的两张图片。')).toBeNull()
    expect(screen.getByRole('button', { name: '批量导入图片' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /查看已填内容与待办/ }))
    const panel = await screen.findByRole('region', { name: '已填内容与待办' })
    expect(within(panel).queryByText('请处理图片保存问题')).toBeNull()
    expect(within(panel).getAllByText('请上传检材照片')).toHaveLength(1)
  }, 15000)

  it('keeps failed and conflicting edits in the guided shell and exposes the existing recovery operations', async () => {
    rejectSave = true
    const failedView = renderPage()
    await selectGuidedAction('请确认检材完整性')
    fireEvent.click(await screen.findByRole('button', { name: '进入下一步' }))
    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('草稿保存失败'))
    const failedAssistantMessage = screen.getByRole('status', { name: '獬豸助手提示' })
    expect(failedAssistantMessage.textContent).toContain('当前输入仍保留在本页面，请重试保存。')
    expect(within(screen.getByRole('group', { name: '请选择操作' })).queryByText('草稿保存失败')).toBeNull()
    const failedDraft = (patchMock.mock.calls.at(-1)?.[1] as { draft: CaseDraft }).draft
    expect(failedDraft.field_states['introduction.evidence_list.completeness'])
      .toEqual(expect.objectContaining({ source: 'user', confirmation: 'confirmed' }))
    expect(screen.getByText('当前输入仍保留在本页面，请重试保存。')).toBeTruthy()

    rejectSave = false
    fireEvent.click(screen.getByRole('button', { name: '重试保存' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: '重试保存' })).toBeNull())

    failedView.unmount(); detailReads = 0; conflictSave = true
    renderPage()
    await selectGuidedAction('请确认检材完整性')
    fireEvent.click(await screen.findByRole('button', { name: '进入下一步' }))
    expect(await screen.findByText('草稿保存发生冲突')).toBeTruthy()
    expect(screen.getByRole('button', { name: '加载服务端版本' })).toBeTruthy()

    conflictSave = false
    fireEvent.click(screen.getByRole('button', { name: '加载服务端版本' }))
    await waitFor(() => expect(screen.queryByText('草稿保存发生冲突')).toBeNull())
  }, 15000)

  it('recovers failed and read-only edit leases from the guided action', async () => {
    leaseFailure = true
    const failedView = renderPage()
    expect(await screen.findByText('编辑权限获取失败，请重新获取后继续。')).toBeTruthy()
    leaseFailure = false
    fireEvent.click(screen.getByRole('button', { name: '重新获取编辑权限' }))
    await waitFor(() => expect(postMock.mock.calls.filter(([url]) => url === API_ENDPOINTS.WORKBENCH_LEASE(caseId))).toHaveLength(2))
    await waitFor(() => expect(screen.queryByRole('button', { name: '重新获取编辑权限' })).toBeNull())

    failedView.unmount(); detailReads = 0; leaseConflict = true
    renderPage()
    expect(await screen.findByText('该案件当前由其他页面占用，当前页面为只读。')).toBeTruthy()
    leaseConflict = false
    fireEvent.click(screen.getByRole('button', { name: '强制接管' }))
    await waitFor(() => expect(postMock.mock.calls.filter(([url, body]) =>
      url === API_ENDPOINTS.WORKBENCH_LEASE(caseId) && (body as { force_takeover?: boolean }).force_takeover,
    )).toHaveLength(1))
  }, 15000)

  async function selectGuidedAction(title: string) {
    fireEvent.click(await screen.findByRole('button', { name: /查看已填内容与待办/ }))
    const panel = await screen.findByRole('region', { name: '已填内容与待办' })
    fireEvent.click(within(panel).getByRole('button', { name: new RegExp(title) }))
  }

  async function editDiscNumber() {
    await screen.findByRole('heading', { name: '獬豸助手', level: 2 })
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_LEASE(caseId), expect.anything()))
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    await selectGuidedAction('介质编号')
    const input = await screen.findByRole('textbox', { name: '介质编号' })
    expect((input as HTMLInputElement).value).toBe('GP20260731-001')
    fireEvent.change(input, { target: { value: 'GP20260731-002' } })
  }

  async function editDiscAndClick() {
    await editDiscNumber()
    await selectGuidedAction('请选择压缩时机')
    fireEvent.click(screen.getByRole('button', { name: /立即开始压缩/ }))
  }

  it('shows the direct compression decision while bounded source review is pending', async () => {
    sourcePending = true
    vi.mocked(window.confirm).mockReturnValue(false)
    renderPage()
    const button = await screen.findByRole('button', { name: /立即开始压缩/ }) as HTMLButtonElement
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)
    await waitFor(() => expect(window.confirm)
      .toHaveBeenCalledWith(expect.stringMatching(/请勿修改、移动或删除源文件/)), { timeout: 5000 })
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
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    const button = screen.getByRole('button', { name: /立即开始压缩/ }) as HTMLButtonElement
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)
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
    expect(await screen.findByText(/其他会话修改/, {}, { timeout: 5000 })).toBeTruthy()
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

  it('saves a newly selected inspector once without entering a PATCH loop', async () => {
    emptyInspectors = true
    renderPage()
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_LEASE(caseId), expect.anything()))
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    await selectGuidedAction('检查人员')

    fireEvent.click(screen.getByRole('button', { name: '添加检查人员' }))
    fireEvent.click(await screen.findByRole('button', { name: '添加张三' }))
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1), { timeout: 5000 })
    await new Promise(resolve => setTimeout(resolve, 1200))
    expect(patchMock).toHaveBeenCalledTimes(1)
  }, 15000)
  it.each(['archive_queued', 'archive_deferred'] as const)('accepts and autosaves a YP number without medium guidance while lifecycle is %s', async lifecycle => {
    initialLifecycle = lifecycle
    renderPage()
    await waitFor(() => expect(screen.queryByText('正在获取编辑租约，请稍候。')).toBeNull())
    await selectGuidedAction('介质编号')
    expect(screen.queryByText(/压缩正在后台进行，可以先填写编号/)).toBeNull()
    expect(screen.queryByText(/最终介质由压缩前归档总量决定，可以先填写编号/)).toBeNull()
    expect(screen.queryByText('GPyyyyMMddXX-序号 · 光盘')).toBeNull()
    expect(screen.queryByText('YPyyyyMMddXX-序号 · 硬盘')).toBeNull()
    fireEvent.change(screen.getByRole('textbox', { name: '介质编号' }), { target: { value: 'YP2026073102-009' } })
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1), { timeout: 5000 })
    const savedDraft = (patchMock.mock.calls[0][1] as { draft: CaseDraft }).draft
    expect(savedDraft.report.attachments.disc_number).toBe('YP2026073102-009')
  }, 15000)

  it('allows repeated disc mapping updates without creating a competing draft revision', async () => {
    archiveResultParts = completedArchiveResult.parts.map(part => ({ ...part, disc_number: '', disc_date: '' }))
    showCompletedArchive = true
    renderPage()
    await selectGuidedAction('介质编号')
    expect(await screen.findByText('待补盘号')).toBeTruthy()
    fireEvent.change(await screen.findByPlaceholderText('如 GP2026073102-01'), { target: { value: 'GP2026073102-01' } })
    fireEvent.click(screen.getByRole('button', { name: /提交盘号映射/ }))
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_ARCHIVE_DISC_MAPPING(caseId), { expected_revision: 5, expected_plan_row_revision: 4, first_disc_number: 'GP2026073102-01' }, { timeout: WORKBENCH_REQUEST_TIMEOUT_MS }))
    await waitFor(() => expect(screen.getByText('归档完成')).toBeTruthy())
    expect((screen.getByRole('textbox', { name: '首个光盘编号' }) as HTMLInputElement).value).toBe('GP2026073102-01')
    await new Promise(resolve => setTimeout(resolve, 800))
    fireEvent.change(screen.getByRole('textbox', { name: '首个光盘编号' }), { target: { value: 'GP2026073102-03' } })
    fireEvent.click(screen.getByRole('button', { name: '更新盘号映射' }))
    await waitFor(() => expect(archivePlanRowRevision).toBe(6))
    expect(patchMock).not.toHaveBeenCalled()
  }, 15000)
  it('blocks browser and SPA navigation until recovered photo bindings finish saving', async () => {
    recoverPhotoOnLoad = true
    holdSave = true
    const view = renderPage()
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))

    await act(async () => { void view.router.navigate(-1) })
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(screen.queryByText('工作台路由')).toBeNull()

    holdSave = false
    await act(async () => { resolveSave?.() })
    resolveSave = null
    await screen.findByText('工作台路由')
  }, 15000)

  it('shows save and exit as soon as manual review completes while archiving continues', async () => {
    showManualReviewComplete = true
    renderPage()
    await screen.findByText('请确认案件简要情况')
    const nextStepButton = screen.getByRole('button', { name: '进入下一步' }) as HTMLButtonElement
    await waitFor(() => expect(nextStepButton.disabled).toBe(false))
    fireEvent.click(nextStepButton)
    await waitFor(() => expect(patchMock).toHaveBeenCalled())
    const savedDraft = (patchMock.mock.calls[0][1] as { draft: CaseDraft }).draft
    expect(savedDraft.field_states['introduction.case_summary.confirmation']).toEqual(expect.objectContaining({
      source: 'user', confirmation: 'confirmed',
    }))
    expect(await screen.findByRole('button', { name: /保存并退出/ })).toBeTruthy()
    expect(screen.getByRole('status', { name: '系统处理状态' }).textContent).toContain('后台归档处理中')
    expect(screen.queryByRole('button', { name: /查看已填内容与待办/ })).toBeNull()
    expect(screen.queryByRole('button', { name: '更新盘号映射' })).toBeNull()
    expect(screen.queryByRole('button', { name: /开始导出|再次导出/ })).toBeNull()
    expect(document.querySelector('.review-editor-form')).toBeNull()
    expect(postMock.mock.calls.some(([url]) => String(url).includes('/export-bundle'))).toBe(false)
  }, 15000)

  it('returns to the workbench from the completed guided review through save and exit', async () => {
    showGuidedReady = true
    showHandledCaseSummary = true
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /保存并退出/ }))
    expect(await screen.findByText('工作台路由')).toBeTruthy()
  }, 15000)

  it('speaks archive completion through the assistant while the reply keeps only mapping controls', async () => {
    showGuidedReady = true
    showHandledCaseSummary = true
    showHandledDiscNumber = true
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: '返回上一步' }))
    await waitFor(() => expect(screen.getByRole('status', { name: '獬豸助手提示' }).textContent)
      .toContain('归档完成'))
    const assistantMessage = screen.getByRole('status', { name: '獬豸助手提示' })
    const reply = screen.getByRole('group', { name: '你的回复' })
    expect(assistantMessage.textContent).toContain('全部 RAR、文件哈希与盘号已对应完成，请返回案件工作台完成导出。')
    expect(within(reply).queryByText('归档完成')).toBeNull()
    expect(within(reply).queryByText(/全部 RAR、文件哈希与盘号已对应完成/)).toBeNull()
    expect(within(reply).getByRole('textbox', { name: '首个光盘编号' })).toBeTruthy()
    expect(within(reply).getByRole('button', { name: '更新盘号映射' })).toBeTruthy()
  }, 15000)

  it('starts immediate compression directly from the deferred terminal outcome', async () => {
    showDeferredTerminal = true
    showHandledCaseSummary = true
    renderPage()

    expect(await screen.findByRole('heading', { name: '草稿已保存' })).toBeTruthy()
    expect(screen.getByText(/压缩已设为稍后处理/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '现在压缩' }))

    await waitFor(() => expect(decisionBodies).toHaveLength(1))
    expect(decisionBodies[0]).toEqual(expect.objectContaining({ decision: 'immediate' }))
  }, 15000)

  it('does not expose a standalone Word export or full editor after archive completion', async () => {
    showCompletedArchive = true
    renderPage()
    await screen.findByRole('heading', { name: '獬豸助手', level: 2 })
    expect(screen.queryByRole('button', { name: /单独导出 Word|导出 Word|完整审核|返回引导模式/ })).toBeNull()
    expect(document.querySelector('.review-editor-form')).toBeNull()
  }, 15000)

  it('shows the exported state for a re-exported case', async () => {
    useExportedLifecycle = true
    renderPage()
    const historyRegion = await screen.findByRole('region', { name: 'Word 内容预览' })
    expect(await within(historyRegion).findByText('文书与委托信息')).toBeTruthy()
    expect(within(historyRegion).queryByText('已完成导出')).toBeNull()
    expect(within(historyRegion).queryByText('案件材料已完成导出')).toBeNull()
    expect(await screen.findByText('已完成导出')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /再次导出|开始导出/ })).toBeNull()
  }, 15000)
})
