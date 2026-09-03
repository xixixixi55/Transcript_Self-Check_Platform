// 第 12 层：FE_Pages — 基于案件 ID、使用旧版生产映射的完整编辑器。
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { SaveOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Space, Spin, message } from 'antd'
import { Link, useBlocker, useNavigate, useParams } from 'react-router-dom'
import { useCaseRecordSession } from '../hooks/useCaseRecordSession'
import { useRecordEditorCatalogs } from '../hooks/useRecordEditorCatalogs'
import { useRecordExport } from '../hooks/useRecordExport'
import { useArchiveCompletion } from '../hooks/useArchiveCompletion'
import { CASE_SUMMARY_CONFIRMATION_FIELD_PATH, findMissingUnextractableReasonIndex, getReviewPendingItems, REVIEW_SECTION_IDS, REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'
import { useReviewPendingNavigation } from '../hooks/useReviewPendingNavigation'
import { useReviewWorkspaceShortcuts as useShortcuts } from '../hooks/useReviewWorkspaceShortcuts'
import { isValidDateFieldValue, isValidMinuteTimeRangeValue, projectEvidenceDerivedContent } from '@biji/shared/utils'
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
import { useGuidedReviewCards } from '../hooks/useGuidedReviewCards'
import { GuidedReviewView } from '../components/GuidedReviewView'
import { GuidedReviewCard } from '../components/GuidedReviewCard'
import ImageUploader from '../components/ImageUploader'

const WORD_EXPORT_PHOTO_WAIT_MS = 5_000

export default function CaseRecordGeneratePage() {
  const { caseId = '' } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const session = useCaseRecordSession(caseId)
  const photoNavigationBlocker = useBlocker(session.photoAssets.navigationUnsafe)
  const { exportDocx, exporting, attachmentWarning, resetAttachmentWarning } = useRecordExport()
  const exportDirectory = useArchiveCompletion()
  const catalogs = useRecordEditorCatalogs()
  const [reviewStatus, setReviewStatus] = useState<ReviewPageStatus>('尚未修改')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [exportPreparing, setExportPreparing] = useState(false)
  const [archiveDecisionBusy, setArchiveDecisionBusy] = useState(false)
  const [reviewMode, setReviewMode] = useState<'guided' | 'full'>('guided')
  const [fullEditorFocusRequest, setFullEditorFocusRequest] = useState({
    targetId: null as string | null, focusInteractive: false, sequence: 0,
  })
  const handledFullEditorFocusSequence = useRef(-1)
  const archiveDecisionInFlight = useRef(false)
  const focusGuidedAfterSwitch = useRef(false)
  const [downloadNameDialogOpen, setDownloadNameDialogOpen] = useState(false)
  useEffect(() => {
    setReviewMode('guided')
    setFullEditorFocusRequest({ targetId: null, focusInteractive: false, sequence: 0 })
    handledFullEditorFocusSequence.current = -1
    focusGuidedAfterSwitch.current = false
    setReviewStatus('尚未修改')
    resetAttachmentWarning()
  }, [caseId, resetAttachmentWarning])
  // 压缩完成前，接受用户输入的任一种介质前缀。
  // 验证结果随后将同一编辑器切换为精确的 GP/YP 契约。
  const archiveMedium = session.completedArchive.result?.archive_medium ?? null
  const projectedReport = useMemo(
    () => session.report ? projectEvidenceDerivedContent(session.report) : null,
    [session.report],
  )
  const pendingItems = useMemo(
    () => projectedReport ? getReviewPendingItems(projectedReport, undefined, archiveMedium, session.draft?.field_states) : [],
    [archiveMedium, projectedReport, session.draft?.field_states],
  )
  const caseSummaryState = session.draft?.field_states[CASE_SUMMARY_CONFIRMATION_FIELD_PATH]
  const caseSummaryReviewed = caseSummaryState?.source === 'user'
    && caseSummaryState.confirmation === 'confirmed'
  const guidedReview = useGuidedReviewCards({
    caseId,
    report: projectedReport,
    fieldStates: session.draft?.field_states,
    pendingItems,
    caseSummaryReviewed,
    lifecycle: session.detail?.shell.lifecycle || 'case_created',
    archiveTask: session.detail?.shell.archive_task_summary,
    archiveMedium,
    archiveParts: session.completedArchive.result?.parts ?? null,
    sourceStatus: session.detail?.source.access_status || 'pending',
    sourceRequiresReselection: Boolean(session.detail?.source.requires_reselection),
    leaseState: session.lease.phase === 'active' && !session.leaseLost ? 'editable'
      : session.lease.phase === 'read_only' ? 'read_only'
        : session.lease.phase === 'expired' || session.leaseLost ? 'expired'
          : session.lease.phase === 'failed' ? 'failed' : 'acquiring',
    saveState: session.autosave.draftState.status,
    saveHasPending: session.autosave.hasPending,
    photoState: attachmentWarning ? 'warning'
      : session.photoAssets.assetError ? 'error'
        : session.photoAssets.uploading ? 'uploading' : 'ready',
    wordExportSucceeded: reviewStatus === '导出成功',
  })
  const { navigateToPendingItem, navigateToSection } = useReviewPendingNavigation()
  const openFullEditor = (targetId?: string, focusInteractive = false) => {
    setFullEditorFocusRequest(current => ({
      targetId: targetId || null,
      focusInteractive,
      sequence: current.sequence + 1,
    }))
    setReviewMode('full')
  }
  useEffect(() => {
    if (reviewMode !== 'full'
      || handledFullEditorFocusSequence.current === fullEditorFocusRequest.sequence) return undefined
    handledFullEditorFocusSequence.current = fullEditorFocusRequest.sequence
    const frame = window.requestAnimationFrame(() => {
      const item = fullEditorFocusRequest.targetId
        ? pendingItems.find(candidate => candidate.targetId === fullEditorFocusRequest.targetId)
        : null
      if (item) navigateToPendingItem(item)
      else if (fullEditorFocusRequest.targetId) {
        const target = document.getElementById(fullEditorFocusRequest.targetId)
        target?.scrollIntoView?.({ block: 'center' })
        const focusTarget = fullEditorFocusRequest.focusInteractive
          ? target?.matches('input, textarea, select')
            ? target
            : target?.querySelector<HTMLElement>('input, textarea, select, [role="button"], button, [tabindex]')
              || (target?.matches('[tabindex]') ? target : null)
          : target
        focusTarget?.focus({ preventScroll: true })
      } else document.getElementById('review-editor-title')?.focus()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [fullEditorFocusRequest, navigateToPendingItem, pendingItems, reviewMode])
  const returnToGuided = () => {
    focusGuidedAfterSwitch.current = true
    setReviewMode('guided')
  }
  useEffect(() => {
    if (reviewMode !== 'guided' || !focusGuidedAfterSwitch.current) return undefined
    const frame = window.requestAnimationFrame(() => {
      document.getElementById('guided-review-conversation-title')?.focus()
      focusGuidedAfterSwitch.current = false
    })
    return () => window.cancelAnimationFrame(frame)
  }, [reviewMode])
  const requestExport = () => {
    if (!projectedReport) return
    const missingIndex = findMissingUnextractableReasonIndex(projectedReport)
    if (missingIndex >= 0) {
      message.warning(`请先填写检材${missingIndex + 1}的无法提取原因，再生成 Word。`)
      const pendingReason = pendingItems.find(item => item.id === `review-evidence-${missingIndex}-unextractable-reason`)
      if (pendingReason) navigateToPendingItem(pendingReason)
      return
    }
    setDownloadNameDialogOpen(true)
  }
  const updateReport = useCallback((path: string, value: unknown) => {
    session.updateReport(path, value)
    if (session.editingEnabled) setReviewStatus('存在未导出修改')
  }, [session.editingEnabled, session.updateReport])
  const handleExport = async (requestedFileName: string) => {
    const detail = session.detail
    if (!session.report || !detail || exporting || exportPreparing || exportDirectory.busy) return false
    setExportPreparing(true)
    try {
      const photosReady = await session.photoAssets.waitForIdle(WORD_EXPORT_PHOTO_WAIT_MS)
      if (!await session.autosave.saveNow()) {
        message.warning('案件仍有未完成保存，完成保存后才能生成 Word。')
        return false
      }
      const preparedDraft = session.autosave.getLastSavedDraft()
      if (!preparedDraft) {
        message.warning('无法确认最新案件版本，请重新加载后再导出。')
        return false
      }
      const report = projectEvidenceDerivedContent(preparedDraft.report)
      const missingReasonIndex = findMissingUnextractableReasonIndex(report)
      if (missingReasonIndex >= 0) {
        message.error(`请填写检材${missingReasonIndex + 1}的无法提取原因后再生成 Word。`)
        return false
      }
      const dateErrors = [
        !isValidDateFieldValue(report.introduction.entrust_time) && '委托时间',
        !isValidMinuteTimeRangeValue(report.introduction.inspection_time_range) && '检查起止时间',
        report.attachments?.burning_date && !isValidDateFieldValue(report.attachments.burning_date) && '附件3刻录时间',
      ].filter(Boolean)
      if (dateErrors.length) { message.error(`请修正以下日期时间字段：${dateErrors.join('、')}`); return false }
      return await runWithSourceExportRiskConfirmation(detail.source.access_status, async () => {
        let files: File[] = []
        if (photosReady) {
          try { files = await session.photoAssets.readFiles() }
          catch { files = [] }
        }
        let chosen
        try { chosen = await exportDirectory.chooseDirectory() }
        catch {
          message.error('本机导出目录选择器暂不可用，请稍后重试。')
          return false
        }
        if ('cancelled' in chosen) return false
        const exportDraft = session.autosave.getLastSavedDraft() ?? preparedDraft
        const exportReport = projectEvidenceDerivedContent(exportDraft.report)
        setReviewStatus('导出中')
        const success = await exportDocx(
          exportReport, files.map(file => file.name), files.length ? files : undefined, requestedFileName,
          null, null, caseId, exportDraft.revision, chosen,
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
  const reacquireLease = () => { void session.lease.acquire(false) }
  const retryDraftSave = async () => {
    if (await session.retrySave()) message.success('当前输入已重新保存。')
    else message.warning('当前输入仍未保存成功，请检查编辑权限后重试。')
  }
  const loadServerDraft = async () => {
    if (!window.confirm('加载服务端版本会替换当前页面尚未保存的输入。确定继续吗？')) return
    try {
      await session.loadServerVersion()
      message.success('已加载服务端版本。')
    } catch {
      message.error('服务端版本加载失败，当前输入仍保留在本页面。')
    }
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
      if (decision === 'deferred') message.success('草稿已保存并稍后处理，可继续审核或安全返回案件列表。')
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
      : session.lease.phase === 'failed' ? '编辑权限获取失败，请重新获取后继续。'
        : session.lease.phase === 'acquiring' ? '正在获取编辑租约，请稍候。' : null
  const archiveCompletionPanel = (
    <ArchiveCompletionPanel lifecycle={session.detail.shell.lifecycle} caseId={caseId}
      expectedRevision={session.detail.shell.revision} parts={session.completedArchive.result?.parts ?? null}
      planRowRevision={session.completedArchive.result?.plan_row_revision ?? null}
      archiveMedium={archiveMedium}
      firstDiscNumber={session.report.attachments?.disc_number || ''}
      onFirstDiscNumberChange={value => updateReport('attachments.disc_number', value)}
      readOnly={!session.editingEnabled}
      onCompleted={() => {
        session.completedArchive.reload()
        void session.reloadDetail(caseId)
      }} />
  )
  const currentGuidedAction = guidedReview.currentAction
  let guidedSpecialContent: React.ReactNode
  if (currentGuidedAction?.kind === 'save_recovery') {
    const saveState = session.autosave.draftState.status
    guidedSpecialContent = <Alert
      type={saveState === 'failed' ? 'error' : saveState === 'conflict' ? 'warning' : 'info'}
      showIcon
      message={saveState === 'failed' ? '草稿保存失败'
        : saveState === 'conflict' ? '草稿保存发生冲突' : '正在重新保存当前输入'}
      description={saveState === 'conflict'
        ? '当前输入仍保留在本页面。可以重试保存，或确认后加载服务端版本。'
        : saveState === 'failed' ? '当前输入仍保留在本页面，请重试保存。'
          : '保存完成前，当前输入会继续保留在本页面。'}
      action={saveState === 'saving' ? undefined : <Space wrap>
        <Button type="primary" onClick={() => { void retryDraftSave() }}>重试保存</Button>
        {saveState === 'conflict' && <Button onClick={() => { void loadServerDraft() }}>加载服务端版本</Button>}
      </Space>} />
  } else if (currentGuidedAction?.kind === 'source_recovery') {
    guidedSpecialContent = <SourceReselectionPanel required onReselect={session.replaceSource} />
  } else if (currentGuidedAction?.kind === 'lease_recovery') {
    guidedSpecialContent = <Alert type="warning" showIcon message={leaseMessage || '当前页面没有有效编辑权限。'}
      action={session.lease.phase === 'read_only'
        ? <Button onClick={forceTakeover}>强制接管</Button>
        : session.lease.phase === 'acquiring' ? undefined
          : <Button onClick={reacquireLease}>重新获取编辑权限</Button>} />
  } else if (currentGuidedAction?.kind === 'photo_recovery') {
    guidedSpecialContent = <Alert type={attachmentWarning ? 'warning' : 'error'} showIcon
      message={attachmentWarning || session.photoAssets.assetError || '图片尚未完成保存。'}
      action={<Button onClick={() => openFullEditor(REVIEW_TARGET_IDS.photos)}>返回图片控件</Button>} />
  } else if (currentGuidedAction?.kind === 'archive_decision'
    || currentGuidedAction?.kind === 'waiting' && ['archive_queued', 'archiving'].includes(session.detail.shell.lifecycle)) {
    guidedSpecialContent = <ArchiveDecisionPanel lifecycle={session.detail.shell.lifecycle} busy={archiveDecisionBusy}
      onImmediate={() => { void chooseArchive('immediate') }} onDeferred={() => { void chooseArchive('deferred') }} />
  } else if (currentGuidedAction?.pendingItem?.targetId === REVIEW_TARGET_IDS.photos) {
    guidedSpecialContent = <ImageUploader materials={session.report.introduction.evidence_list || []}
      photos={session.photoAssets.files} onChange={session.photoAssets.handleChange} />
  } else if (currentGuidedAction?.pendingItem?.targetId === REVIEW_TARGET_IDS.discNumber) {
    guidedSpecialContent = archiveCompletionPanel
  } else if (currentGuidedAction?.kind === 'ready') {
    guidedSpecialContent = <Button type="primary" size="large" icon={<SaveOutlined />}
      loading={session.autosave.draftState.status === 'saving' || session.photoAssets.navigationUnsafe}
      disabled={!session.editingEnabled}
      onClick={() => { void handleBackToWorkbench() }}>保存并退出</Button>
  }
  const guidedInteractionDisabled = !session.editingEnabled
    || exportPreparing || exportDirectory.busy || exporting
  const confirmCurrentGuidedField = () => {
    const targetId = currentGuidedAction?.pendingItem?.targetId
    if (targetId === REVIEW_TARGET_IDS.caseSummary) {
      session.setCaseSummaryConfirmed(true)
      if (session.editingEnabled) setReviewStatus('存在未导出修改')
    }
    if (targetId === REVIEW_TARGET_IDS.evidenceCompleteness) {
      session.setEvidenceCompletenessConfirmed(true)
      if (session.editingEnabled) setReviewStatus('存在未导出修改')
    }
  }
  const confirmCurrentGuidedAction = () => {
    confirmCurrentGuidedField()
    guidedReview.confirmCurrentAction()
  }
  const returnToNextGuidedAction = () => {
    confirmCurrentGuidedField()
    guidedReview.returnToNextAction()
  }
  return (
    <>
      <div className={`review-page${reviewMode === 'guided' ? ' review-page--guided' : ''}`}>
        {reviewMode === 'full' && (
          <ReviewPageHeader report={session.report} onPreview={() => setPreviewOpen(true)} />
        )}
        {reviewMode === 'guided' && currentGuidedAction ? (
          <GuidedReviewView conversationKey={caseId} history={guidedReview.history}
            previouslyHandledFields={guidedReview.previouslyHandledFields} currentAction={currentGuidedAction}
            allActions={guidedReview.allActions} hasResponse={Boolean(guidedSpecialContent || currentGuidedAction.pendingItem)}
            onSelectAction={guidedReview.selectAction}
            onRevisitAction={guidedReview.revisitAction}
            onRevisitHandledField={guidedReview.revisitHandledField}
            onConfirmCurrentAction={confirmCurrentGuidedAction}
            confirmCurrentActionDisabled={guidedInteractionDisabled}
            canReturnToPrevious={guidedReview.canReturnToPrevious}
            canReturnToNext={guidedReview.canReturnToNext}
            onReturnToPreviousAction={guidedReview.returnToPreviousAction}
            onReturnToNextAction={returnToNextGuidedAction}
            onOpenFullEditor={openFullEditor}
            onBackToWorkbench={() => { void handleBackToWorkbench() }}>
            <GuidedReviewCard action={currentGuidedAction} report={projectedReport || session.report}
              updateReport={updateReport}
              readOnly={guidedInteractionDisabled}
              specialContent={guidedSpecialContent}
              onEvidenceCompletenessChange={confirmed => {
                session.setEvidenceCompletenessConfirmed(confirmed)
                if (session.editingEnabled) setReviewStatus('存在未导出修改')
              }}
              onOpenFullEditor={openFullEditor} />
          </GuidedReviewView>
        ) : reviewMode === 'full' ? <div className="review-full-workspace">
          <SourceReselectionPanel required={sourceInvalid} onReselect={session.replaceSource} />
          {sourcePending && <Alert className="case-workbench-page__toolbar" type="warning" showIcon message="报告来源待快速复核" description="可直接选择压缩时机；开始压缩前会快速核对授权路径、报告结构和核心报告文件。" />}
          {!sourceInvalid && (
            <section className="review-preflight" aria-labelledby="review-preflight-title">
              <div className="review-preflight__heading">
                <div>
                  <h2 id="review-preflight-title">归档准备</h2>
                  <p>确认压缩时机与介质编号，不影响下方笔录审核。</p>
                </div>
              </div>
              <div className="review-preflight__items">
                <div className="review-preflight__item">
                  <ArchiveDecisionPanel lifecycle={session.detail.shell.lifecycle} busy={archiveDecisionBusy}
                    onImmediate={() => { void chooseArchive('immediate') }} onDeferred={() => { void chooseArchive('deferred') }} />
                </div>
                <div id={REVIEW_SECTION_IDS.archive}
                  className="review-preflight__item review-navigation-target" tabIndex={-1}>
                  {archiveCompletionPanel}
                </div>
              </div>
            </section>
          )}
          {leaseMessage && <Alert className="case-workbench-page__toolbar"
            type={session.lease.phase === 'failed' ? 'error' : 'warning'} showIcon message={leaseMessage}
            action={session.lease.phase === 'read_only'
              ? <Button onClick={forceTakeover}>强制接管</Button>
              : session.lease.phase === 'acquiring' ? undefined
                : <Button onClick={reacquireLease}>重新获取编辑权限</Button>} />}
          {(attachmentWarning || session.photoAssets.assetError) && <Alert
            className="case-workbench-page__toolbar"
            type={attachmentWarning ? 'warning' : 'error'}
            showIcon
            message={attachmentWarning || session.photoAssets.assetError}
            action={<Button onClick={() => openFullEditor(REVIEW_TARGET_IDS.photos)}>返回图片控件</Button>} />}
          <ReviewPendingSummary variant="side" items={pendingItems}
            onNavigate={navigateToPendingItem} onNavigateSection={navigateToSection} />
          <RecordEditorForm
            report={projectedReport || session.report}
            updateReport={updateReport}
            onExport={requestExport}
            exporting={exporting || exportPreparing || exportDirectory.busy}
            onBackToUpload={() => { void handleBackToWorkbench() }}
            onReturnToGuided={returnToGuided}
            deviceOptions={catalogs.deviceOptions}
            availableInspectors={catalogs.inspectors}
            inspectorLoading={catalogs.inspectorLoading}
            inspectorError={catalogs.inspectorError}
            photoFiles={session.photoAssets.files}
            onPhotoFilesChange={session.photoAssets.handleChange}
            fieldStates={session.draft?.field_states}
            onEvidenceCompletenessChange={confirmed => {
              session.setEvidenceCompletenessConfirmed(confirmed)
              if (session.editingEnabled) setReviewStatus('存在未导出修改')
            }}
            saveStatus={reviewStatus}
            saveBusy={session.photoAssets.uploading || session.autosave.draftState.status === 'saving'}
            onSave={saveNow}
            pendingItems={pendingItems}
            workbenchMode
            readOnly={!session.editingEnabled || exportPreparing || exportDirectory.busy || exporting}
            archiveContextId={null}
            archiveResult={session.completedArchive}
          />
        </div> : null}
      </div>
      <WordDownloadNameDialog
        open={downloadNameDialogOpen}
        documentNumber={session.report.document_number}
        exporting={exporting || exportPreparing || exportDirectory.busy}
        onCancel={() => setDownloadNameDialogOpen(false)}
        onConfirm={downloadName => { setDownloadNameDialogOpen(false); void handleExport(downloadName) }}
      />
      <ReviewPreviewDrawer open={previewOpen} report={projectedReport || session.report} photoFiles={session.photoAssets.files} onClose={() => setPreviewOpen(false)} />
    </>
  )
}
