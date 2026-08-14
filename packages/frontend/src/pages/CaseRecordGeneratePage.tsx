// Layer 12: FE_Pages — case-id based full editor using the Legacy production mappings.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Card, Spin, message } from 'antd'
import { Link, useBlocker, useNavigate, useParams } from 'react-router-dom'
import type { InspectorLibraryRecord } from '@biji/shared/types'
import { useCaseRecordSession } from '../hooks/useCaseRecordSession'
import { useRecordExport } from '../hooks/useRecordExport'
import { useArchiveCompletion } from '../hooks/useArchiveCompletion'
import { getReviewPendingItems, REVIEW_SECTION_IDS } from '../hooks/useReviewChecklist'
import { useReviewPendingNavigation } from '../hooks/useReviewPendingNavigation'
import { useReviewWorkspaceShortcuts as useShortcuts } from '../hooks/useReviewWorkspaceShortcuts'
import { isValidDateFieldValue, isValidMinuteTimeRangeValue } from '@biji/shared/utils'
import { API_ENDPOINTS } from '@biji/shared/constants'
import axios from 'axios'
import RecordEditorForm from '../components/RecordEditorForm'
import { ReviewPageHeader } from '../components/ReviewPageHeader'
import { ReviewPendingSummary } from '../components/ReviewPendingSummary'
import { ReviewPreviewDrawer } from '../components/ReviewPreviewDrawer'
import { CaseStatusBadge } from '../components/CaseStatusBadge'
import { SourceReselectionPanel } from '../components/SourceReselectionPanel'
import { ArchiveDecisionPanel } from '../components/ArchiveDecisionPanel'
import { ArchiveCompletionPanel } from '../components/ArchiveCompletionPanel'
import { WordDownloadNameDialog } from '../components/WordDownloadNameDialog'
import type { ReviewPageStatus } from '../components/reviewWorkspaceTypes'
import { runWithSourceExportRiskConfirmation } from '../hooks/useSourceExportRisk'
export default function CaseRecordGeneratePage() {
  const { caseId = '' } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const session = useCaseRecordSession(caseId)
  const photoNavigationBlocker = useBlocker(session.photoAssets.navigationUnsafe)
  const { exportDocx, exporting } = useRecordExport()
  const exportDirectory = useArchiveCompletion()
  const [devices, setDevices] = useState<{ id: string; name: string; model: string }[]>([])
  const [inspectors, setInspectors] = useState<InspectorLibraryRecord[]>([])
  const [reviewStatus, setReviewStatus] = useState<ReviewPageStatus>('尚未修改')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [exportPreparing, setExportPreparing] = useState(false)
  const [inspectorError, setInspectorError] = useState<string | null>(null)
  const [inspectorLoading, setInspectorLoading] = useState(false)
  const [archiveDecisionBusy, setArchiveDecisionBusy] = useState(false)
  const archiveDecisionInFlight = useRef(false)
  const [downloadNameDialogOpen, setDownloadNameDialogOpen] = useState(false)
  useEffect(() => {
    axios.get(API_ENDPOINTS.DEVICES).then(response => setDevices(response.data.data || [])).catch(() => undefined)
    setInspectorLoading(true)
    axios.get(API_ENDPOINTS.INSPECTORS, { params: { enabled_only: true } })
      .then(response => setInspectors(response.data.data || []))
      .finally(() => setInspectorLoading(false))
      .catch(() => setInspectorError('获取启用检查人员失败，请稍后重试。'))
  }, [])
  const pendingItems = useMemo(() => session.report ? getReviewPendingItems(session.report) : [], [session.report])
  const { navigateToPendingItem, navigateToSection } = useReviewPendingNavigation()
  const updateReport = useCallback((path: string, value: unknown) => {
    session.updateReport(path, value)
    if (session.editingEnabled) setReviewStatus('存在未导出修改')
  }, [session.editingEnabled, session.updateReport])
  const handleExport = async (requestedFileName: string) => {
    const detail = session.detail
    if (!session.report || !detail || exporting || exportPreparing || exportDirectory.busy) return false
    setExportPreparing(true)
    try {
      if (session.photoAssets.uploading) {
        message.warning('图片仍在保存，请完成图片保存后再生成 Word。')
        return false
      }
      if (!await session.autosave.saveNow()) {
        message.warning('案件仍有未完成保存，完成保存后才能生成 Word。')
        return false
      }
      const savedDraft = session.autosave.getLastSavedDraft()
      if (!savedDraft) {
        message.warning('无法确认最新案件版本，请重新加载后再导出。')
        return false
      }
      const report = savedDraft.report
      const dateErrors = [
        !isValidDateFieldValue(report.introduction.entrust_time) && '委托时间',
        !isValidMinuteTimeRangeValue(report.introduction.inspection_time_range) && '检查起止时间',
        report.attachments?.burning_date && !isValidDateFieldValue(report.attachments.burning_date) && '附件3刻录时间',
      ].filter(Boolean)
      if (dateErrors.length) { message.error(`请修正以下日期时间字段：${dateErrors.join('、')}`); return false }
      return await runWithSourceExportRiskConfirmation(detail.source.access_status, async () => {
        let files: File[]
        try { files = await session.photoAssets.readFiles() }
        catch { return false }
        let chosen
        try { chosen = await exportDirectory.chooseDirectory() }
        catch {
          message.error('本机导出目录选择器暂不可用，请稍后重试。')
          return false
        }
        if ('cancelled' in chosen) return false
        setReviewStatus('导出中')
        const success = await exportDocx(
          report, files.map(file => file.name), files.length ? files : undefined, requestedFileName,
          null, null, caseId, savedDraft.revision, chosen,
        )
        setReviewStatus(success ? '导出成功' : '导出失败')
        if (success) message.success(`Word 已导出至：${chosen.path}`)
        return success
      })
    } finally {
      setExportPreparing(false)
    }
  }
  const saveNow = () => {
    if (!session.editingEnabled) { message.warning('当前页面没有有效编辑租约，未写入案件。'); return }
    void session.autosave.saveNow()
  }
  const forceTakeover = () => {
    if (window.confirm('当前案件可能仍由其他页面编辑。强制接管会使旧页面失去写入资格，并记录本地会话审计。确定继续吗？')) void session.lease.acquire(true)
  }
  const chooseArchive = async (decision: 'immediate' | 'deferred') => {
    if (archiveDecisionInFlight.current) return
    if (!session.editingEnabled) { message.warning('当前页面没有有效编辑租约，不能修改压缩决策。'); return }
    if (decision === 'immediate' && !window.confirm(
      '压缩将直接读取源报告目录。\n\n压缩期间请勿修改、移动或删除源文件，也不要继续使用取证软件向该目录写入数据。\n\n请确认报告已生成完成并开始压缩。',
    )) return
    archiveDecisionInFlight.current = true
    setArchiveDecisionBusy(true)
    try {
      if (decision === 'immediate') {
        const saved = await session.autosave.saveNow()
        if (!saved) {
          message.warning('当前输入尚未保存成功，请先完成保存后再开始压缩。')
          return
        }
      }
      const result = await session.decideArchive(decision)
      if (result.archive_task) message.success('归档任务已进入后台队列，可在案件卡片查看状态。')
      if (decision === 'deferred') message.info('已选择稍后压缩，案件和草稿已保留。')
    } catch (error) {
      const responseCode = (error as { response?: { data?: { detail?: { code?: string } } } })?.response?.data?.detail?.code
      if (responseCode === 'REVISION_CONFLICT') {
        message.error('案件已被其他会话修改，当前压缩未启动；请加载服务端版本并确认后再操作。')
      } else if (responseCode === 'EDIT_LEASE_REQUIRED' || responseCode === 'EDIT_LEASE_LOST') {
        message.error('编辑租约已失效，当前压缩未启动；请重新获取编辑权限后再操作。')
      } else {
        message.error('压缩决策未完成，请检查案件保存状态后再试。')
      }
    } finally {
      archiveDecisionInFlight.current = false
      setArchiveDecisionBusy(false)
    }
  }
  useShortcuts({ onSave: saveNow, previewOpen, onClosePreview: () => setPreviewOpen(false), enabled: Boolean(session.report) })
  useEffect(() => {
    const shouldWarn = session.photoAssets.navigationUnsafe || session.autosave.hasPending || session.autosave.draftState.status === 'saving'
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!shouldWarn) return
      event.preventDefault()
      event.returnValue = '案件仍有未完成保存，请确认是否离开。'
    }
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [session.autosave.draftState.status, session.autosave.hasPending, session.photoAssets.navigationUnsafe])
  useEffect(() => {
    if (photoNavigationBlocker.state !== 'blocked') return undefined
    let active = true
    const { proceed, reset } = photoNavigationBlocker
    message.info('正在完成图片上传与草稿保存，请稍候。')
    void session.photoAssets.waitForIdle().then(saved => {
      if (!active) return
      if (saved) proceed()
      else {
        reset()
        message.warning('图片尚未成功保存到案件草稿，请完成保存后再切换案件。')
      }
    })
    return () => { active = false }
  }, [photoNavigationBlocker.state, session.photoAssets.waitForIdle])

  const handleBackToWorkbench = async () => {
    if (session.photoAssets.navigationUnsafe) {
      message.info('正在完成图片上传与草稿保存，请稍候。')
      if (!await session.photoAssets.waitForIdle()) {
        message.warning('图片尚未成功保存到案件草稿，请完成保存后再切换案件。')
        return
      }
    }
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
  const sourceInvalid = session.detail.source.requires_reselection || ['invalid', 'requires_reselection'].includes(session.detail.source.access_status)
  const sourcePending = session.detail.source.access_status === 'pending'
  const leaseMessage = session.lease.phase === 'read_only' ? '该案件当前由其他页面占用，当前页面为只读。'
    : session.lease.phase === 'expired' || session.leaseLost ? '编辑租约已失效，已停止自动保存。请重新获取租约后继续。'
      : session.lease.phase === 'acquiring' ? '正在获取编辑租约，请稍候。' : null
  return (
    <>
      <div className="review-page">
        <ReviewPageHeader report={session.report} status={reviewStatus} onPreview={() => setPreviewOpen(true)} />
        <SourceReselectionPanel required={sourceInvalid} onReselect={session.replaceSource} />
        {sourcePending && <Alert className="case-workbench-page__toolbar" type="warning" showIcon message="报告来源待快速复核" description="可直接选择压缩时机；开始压缩前会快速核对授权路径、报告结构和核心报告文件。" />}
        {!sourceInvalid && <>
          <ArchiveDecisionPanel lifecycle={session.detail.shell.lifecycle} busy={archiveDecisionBusy} onImmediate={() => { void chooseArchive('immediate') }} onDeferred={() => { void chooseArchive('deferred') }} />
          <div id={REVIEW_SECTION_IDS.archive} className="review-navigation-target" tabIndex={-1}>
          <ArchiveCompletionPanel lifecycle={session.detail.shell.lifecycle} caseId={caseId}
            expectedRevision={session.detail.shell.revision} parts={session.completedArchive.result?.parts ?? null}
            planRowRevision={session.completedArchive.result?.plan_row_revision ?? null}
            firstDiscNumber={session.report.attachments?.disc_number || ''}
            onFirstDiscNumberChange={value => updateReport('attachments.disc_number', value)}
            readOnly={!session.editingEnabled} defaultWordName={session.report.document_number}
            onCompleted={() => {
              session.completedArchive.reload()
              void session.reloadDetail(caseId)
            }} />
          </div>
        </>}
        {leaseMessage && <Alert className="case-workbench-page__toolbar" type="warning" showIcon message={leaseMessage} action={session.lease.phase === 'read_only' ? <Button onClick={forceTakeover}>强制接管</Button> : undefined} />}
        {session.lease.phase === 'failed' && <Alert className="case-workbench-page__toolbar" type="error" showIcon message="编辑租约获取失败，请刷新后重试。" />}
        {session.photoAssets.assetError && <Alert className="case-workbench-page__toolbar" type="error" showIcon message={session.photoAssets.assetError} />}
        <ReviewPendingSummary variant="side" items={pendingItems}
          onNavigate={navigateToPendingItem} onNavigateSection={navigateToSection} />
        <RecordEditorForm
          report={session.report}
          updateReport={updateReport}
          onExport={() => setDownloadNameDialogOpen(true)}
          exporting={exporting || exportPreparing || exportDirectory.busy}
          onBackToUpload={() => { void handleBackToWorkbench() }}
          deviceOptions={devices.map(device => ({ label: `${device.name} (${device.model})`, value: device.name }))}
          availableInspectors={inspectors}
          inspectorLoading={inspectorLoading}
          inspectorError={inspectorError}
          photoFiles={session.photoAssets.files}
          onPhotoFilesChange={session.photoAssets.handleChange}
          fieldStates={session.draft?.field_states}
          saveStatus={reviewStatus}
          saveBusy={session.photoAssets.uploading || session.autosave.draftState.status === 'saving'}
          onSave={saveNow}
          pendingItems={pendingItems}
          workbenchMode
          readOnly={!session.editingEnabled || exportPreparing || exportDirectory.busy || exporting}
          archiveContextId={null}
          archiveResult={session.completedArchive}
        />
      </div>
      <WordDownloadNameDialog
        open={downloadNameDialogOpen}
        documentNumber={session.report.document_number}
        exporting={exporting || exportPreparing || exportDirectory.busy}
        onCancel={() => setDownloadNameDialogOpen(false)}
        onConfirm={downloadName => { setDownloadNameDialogOpen(false); void handleExport(downloadName) }}
      />
      <ReviewPreviewDrawer open={previewOpen} report={session.report} photoFiles={session.photoAssets.files} onClose={() => setPreviewOpen(false)} />
    </>
  )
}
