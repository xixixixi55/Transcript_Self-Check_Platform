// Layer 12: FE_Pages — case-id based full editor using the Legacy production mappings.
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Spin, Steps, message } from 'antd'
import { Link, useNavigate, useParams } from 'react-router-dom'
import type { InspectorLibraryRecord } from '@biji/shared/types'
import { useCaseRecordSession } from '../hooks/useCaseRecordSession'
import { useRecordExport } from '../hooks/useRecordExport'
import { useArchivePreparation } from '../hooks/useArchivePreparation'
import { getReviewPendingItems } from '../hooks/useReviewChecklist'
import { useReviewWorkspaceShortcuts as useShortcuts } from '../hooks/useReviewWorkspaceShortcuts'
import { isValidDateFieldValue, isValidMinuteTimeRangeValue } from '@biji/shared/utils'
import { API_ENDPOINTS } from '@biji/shared/constants'
import axios from 'axios'
import RecordEditorForm from '../components/RecordEditorForm'
import { ReviewPageHeader } from '../components/ReviewPageHeader'
import { ReviewPendingSummary } from '../components/ReviewPendingSummary'
import { ReviewPreviewDrawer } from '../components/ReviewPreviewDrawer'
import { CaseStatusBadge } from '../components/CaseStatusBadge'
import { CaseSaveStatusPanel } from '../components/CaseSaveStatusPanel'
import { FieldProvenanceBadge } from '../components/FieldProvenanceBadge'
import { SourceReselectionPanel } from '../components/SourceReselectionPanel'
import { ArchiveDecisionPanel } from '../components/ArchiveDecisionPanel'
import type { ReviewPageStatus } from '../components/reviewWorkspaceTypes'
import { useCaseExportSettings } from '../hooks/useCaseExportSettings'
export default function CaseRecordGeneratePage() {
  const { caseId = '' } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const session = useCaseRecordSession(caseId)
  const { exportDocx, exporting } = useRecordExport()
  const archive = useArchivePreparation()
  const [devices, setDevices] = useState<{ id: string; name: string; model: string }[]>([])
  const [inspectors, setInspectors] = useState<InspectorLibraryRecord[]>([])
  const [reviewStatus, setReviewStatus] = useState<ReviewPageStatus>('尚未修改')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [inspectorError, setInspectorError] = useState<string | null>(null)
  const [inspectorLoading, setInspectorLoading] = useState(false)
  const [archiveContextId, setArchiveContextId] = useState<string | null>(null)
  const [archiveAttemptId, setArchiveAttemptId] = useState<string | null>(null)
  const [archiveDecisionBusy, setArchiveDecisionBusy] = useState(false)
  const [defaultDiscPrefix, setDefaultDiscPrefix] = useState('')
  useEffect(() => {
    setArchiveContextId(null)
    setArchiveAttemptId(null)
    archive.reset()
  }, [archive.reset, caseId])
  useEffect(() => {
    axios.get(API_ENDPOINTS.DEVICES).then(response => setDevices(response.data.data || [])).catch(() => undefined)
    setInspectorLoading(true)
    axios.get(API_ENDPOINTS.INSPECTORS, { params: { enabled_only: true } })
      .then(response => setInspectors(response.data.data || []))
      .finally(() => setInspectorLoading(false))
      .catch(() => setInspectorError('获取启用检查人员失败，请稍后重试。'))
  }, [])
  useEffect(() => {
    if (session.defaults) setDefaultDiscPrefix(session.defaults.disc_number_prefix)
  }, [session.defaults?.revision])
  const exportSettings = useCaseExportSettings(session.report)
  const {
    customFileName, exportFileName, exportFileNameError,
    setCustomFileName, setFileName: setExportFileName, setExportFileNameError,
  } = exportSettings
  const pendingItems = useMemo(() => session.report
    ? getReviewPendingItems(session.report, exportSettings.customFileName ? exportSettings.exportFileNameError : undefined)
    : [], [exportSettings.customFileName, exportSettings.exportFileNameError, session.report])
  const updateReport = useCallback((path: string, value: unknown) => {
    session.updateReport(path, value)
    if (session.editingEnabled) setReviewStatus('存在未导出修改')
  }, [session.editingEnabled, session.updateReport])
  const handleExport = async () => {
    const report = session.report
    if (!report || exporting) return false
    const dateErrors = [
      !isValidDateFieldValue(report.introduction.entrust_time) && '委托时间',
      !isValidMinuteTimeRangeValue(report.introduction.inspection_time_range) && '检查起止时间',
      report.attachments?.burning_date && !isValidDateFieldValue(report.attachments.burning_date) && '附件3刻录时间',
    ].filter(Boolean)
    if (dateErrors.length) { message.error(`请修正以下日期时间字段：${dateErrors.join('、')}`); return false }
    const requestedFileName = exportSettings.requestedFileName
    if (customFileName) {
      const error = exportSettings.validate()
      if (error) {
        setExportFileNameError(error)
        message.error(error)
        return false
      }
    }
    setReviewStatus('导出中')
    let files: File[]
    try { files = await session.photoAssets.readFiles() }
    catch { return false }
    const success = await exportDocx(
      report, files.map(file => file.name), files.length ? files : undefined, requestedFileName,
      archive.manifest ? archiveContextId : null, archive.manifest?.manifest_id ?? null,
    )
    setReviewStatus(success ? '导出成功' : '导出失败')
    return success
  }
  const saveReportDefaults = async () => {
    const saved = await session.saveSharedDefaults(defaultDiscPrefix)
    if (saved) message.success('共享默认值已保存')
    else message.error('共享默认值保存失败，当前输入仍保留')
  }
  const clearReportDefaults = async () => {
    const cleared = await session.clearSharedDefaults()
    if (cleared) {
      setDefaultDiscPrefix('')
      message.success('共享默认值已清除')
    } else message.error('共享默认值清除失败，当前输入仍保留')
  }
  const saveNow = () => {
    if (!session.editingEnabled) { message.warning('当前页面没有有效编辑租约，未写入案件。'); return }
    void session.autosave.saveNow()
  }
  const loadServer = async () => {
    try { await session.loadServerVersion(); message.info('已加载服务端版本，当前未保存输入已放弃。') }
    catch { message.error('服务端版本加载失败，请稍后重试。') }
  }
  const forceTakeover = () => {
    if (window.confirm('当前案件可能仍由其他页面编辑。强制接管会使旧页面失去写入资格，并记录本地会话审计。确定继续吗？')) void session.lease.acquire(true)
  }
  const chooseArchive = async (decision: 'immediate' | 'deferred') => {
    if (!session.editingEnabled) { message.warning('当前页面没有有效编辑租约，不能修改压缩决策。'); return }
    setArchiveDecisionBusy(true)
    try {
      if (decision === 'immediate' && session.autosave.hasPending && !await session.autosave.saveNow()) {
        message.warning('当前输入尚未保存成功，请先完成保存后再开始压缩。')
        return
      }
      const result = await session.decideArchive(decision)
      setArchiveContextId(result.archive_context_id)
      setArchiveAttemptId(result.archive_attempt_id || null)
      if (result.archive_context_id && session.report) {
        await archive.prepare(session.report, result.archive_context_id, result.archive_attempt_id)
      }
      if (decision === 'deferred') message.info('已选择稍后压缩，案件和草稿已保留。')
    } catch { message.error('压缩决策未完成，请刷新案件后重试。') }
    finally { setArchiveDecisionBusy(false) }
  }
  const hasReportDefaults = Boolean(session.defaults && (
    session.defaults.document_number || session.defaults.inspection_place
    || session.defaults.inspection_method || session.defaults.hardware_device
    || session.defaults.inspector_order.length || session.defaults.disc_number_prefix
  ))
  useShortcuts({ onSave: saveNow, previewOpen, onClosePreview: () => setPreviewOpen(false), enabled: Boolean(session.report) })
  useEffect(() => {
    const shouldWarn = session.autosave.hasPending || session.autosave.draftState.status === 'saving'
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!shouldWarn) return
      event.preventDefault()
      event.returnValue = '案件仍有未完成保存，请确认是否离开。'
    }
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [session.autosave.draftState.status, session.autosave.hasPending])

  const handleBackToWorkbench = async () => {
    if (session.autosave.hasPending || session.autosave.draftState.status === 'saving') {
      if (!session.editingEnabled || !await session.autosave.saveNow()) {
        message.warning('当前输入尚未成功保存，仍保留在本页面；请完成保存后再切换案件。')
        return
      }
    }
    navigate('/electronic-inspection/workbench')
  }
  if (session.detailLoading) return <div className="platform-flow-page"><Spin size="large" style={{ display: 'block', margin: '100px auto' }} /></div>
  if (session.detailError || !session.detail) return <div className="platform-flow-page"><Alert type="error" showIcon message={session.detailError?.message || '案件不存在或暂时无法加载。'} action={<Link to="/electronic-inspection/workbench"><Button>返回案件工作台</Button></Link>} /></div>
  if (!session.report) return (
    <div className="platform-flow-page">
      <Card title={session.detail.shell.case_name || '未命名案件'} extra={<CaseStatusBadge lifecycle={session.detail.shell.lifecycle} task={session.parseTask || session.detail.parse_task} />}>
        <p>{session.parseTask?.error_summary || '案件尚未生成可审核草稿，当前不能审核、归档或导出。'}</p>
        {(session.parseTask?.status === 'failed_retryable' || session.parseTask?.status === 'interrupted') && <Button onClick={() => { void session.retryCase(caseId) }}>重试解析</Button>}
        <Link to="/electronic-inspection/workbench"><Button style={{ marginLeft: 8 }}>返回工作台</Button></Link>
      </Card>
    </div>
  )

  const sourceInvalid = session.detail.source.requires_reselection
    || session.detail.source.access_status === 'invalid'
    || session.detail.source.access_status === 'requires_reselection'
  const sourcePending = session.detail.source.access_status === 'pending'
  const leaseMessage = session.lease.phase === 'read_only' ? '该案件当前由其他页面占用，当前页面为只读。'
    : session.lease.phase === 'expired' || session.leaseLost ? '编辑租约已失效，已停止自动保存。请重新获取租约后继续。'
      : session.lease.phase === 'acquiring' ? '正在获取编辑租约，请稍候。' : null
  return (
    <>
      <div className="review-page">
        <ReviewPageHeader report={session.report} status={reviewStatus} onPreview={() => setPreviewOpen(true)} />
        <Steps current={1} className="review-steps"><Steps.Step title="案件工作台" /><Steps.Step title="审核编辑" /><Steps.Step title="导出 Word" /></Steps>
        <SourceReselectionPanel required={sourceInvalid} onReselect={session.replaceSource} />
        {sourcePending && <Alert className="case-workbench-page__toolbar" type="warning" showIcon message="报告来源待复核" description="来源可信状态尚未完成确认；草稿仍可查看和编辑，正式 Word 和压缩将在复核完成后开放。" />}
        {!sourceInvalid && !sourcePending && <ArchiveDecisionPanel
            lifecycle={session.detail.shell.lifecycle}
            busy={archiveDecisionBusy}
            contextReady={Boolean(archiveContextId)}
            onImmediate={() => { void chooseArchive('immediate') }}
            onDeferred={() => { void chooseArchive('deferred') }}
          />}
        {leaseMessage && <Alert className="case-workbench-page__toolbar" type="warning" showIcon message={leaseMessage} action={session.lease.phase === 'read_only' ? <Button onClick={forceTakeover}>强制接管</Button> : undefined} />}
        {session.lease.phase === 'failed' && <Alert className="case-workbench-page__toolbar" type="error" showIcon message="编辑租约获取失败，请刷新后重试。" />}
        <CaseSaveStatusPanel draft={session.autosave.draftState}
          sharedDefaults={session.sharedDefaultsSaveState.status === 'not_changed'
            ? session.autosave.sharedState : session.sharedDefaultsSaveState}
          onRetry={() => { void session.autosave.retry() }} onLoadServer={() => { void loadServer() }} />
        {session.photoAssets.assetError && <Alert className="case-workbench-page__toolbar" type="error" showIcon message={session.photoAssets.assetError} />}
        <div className="case-workbench-page__toolbar">文号来源：<FieldProvenanceBadge state={session.draft?.field_states.document_number} /></div>
        <ReviewPendingSummary items={pendingItems} onNavigate={sectionId => document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth' })} />
        <RecordEditorForm
          report={session.report}
          updateReport={updateReport}
          onExport={handleExport}
          exporting={exporting}
          onBackToUpload={() => { void handleBackToWorkbench() }}
          deviceOptions={devices.map(device => ({ label: `${device.name} (${device.model})`, value: device.name }))}
          availableInspectors={inspectors}
          inspectorLoading={inspectorLoading}
          inspectorError={inspectorError}
          photoFiles={session.photoAssets.files}
          onPhotoFilesChange={session.photoAssets.handleChange}
          exportFileName={exportFileName}
          customFileName={customFileName}
          exportFileNameError={exportFileNameError}
          onCustomFileNameChange={setCustomFileName}
          onExportFileNameChange={setExportFileName}
          hasReportDefaults={hasReportDefaults}
          defaultDiscPrefix={defaultDiscPrefix}
          onSaveReportDefaults={() => { void saveReportDefaults() }}
          onClearReportDefaults={() => { void clearReportDefaults() }}
          onDefaultDiscPrefixChange={setDefaultDiscPrefix}
          saveStatus={reviewStatus}
          saveBusy={session.autosave.draftState.status === 'saving'}
          onSave={saveNow}
          pendingItems={pendingItems}
          workbenchMode
          readOnly={!session.editingEnabled}
          draftSaveStatus={session.autosave.draftState.status}
          sharedDefaultsSaveStatus={session.sharedDefaultsSaveState.status === 'not_changed'
            ? session.autosave.sharedState.status : session.sharedDefaultsSaveState.status}
          archiveContextId={archiveContextId}
          archiveStatus={archive.status}
          archivePreparing={archive.loading}
          onPrepareArchive={() => { if (session.report && archiveContextId) void archive.prepare(session.report, archiveContextId, archiveAttemptId) }}
          archiveManifest={archive.manifest}
          archiveError={archive.error}
        />
      </div>
      <ReviewPreviewDrawer open={previewOpen} report={session.report} photoFiles={session.photoAssets.files} onClose={() => setPreviewOpen(false)} />
    </>
  )
}
