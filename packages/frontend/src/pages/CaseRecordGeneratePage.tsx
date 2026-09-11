// 第 12 层：FE_Pages — 基于案件 ID、使用旧版生产映射的完整编辑器。
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { SaveOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Space, Spin, message } from 'antd'
import { Link, useBlocker, useNavigate, useParams } from 'react-router-dom'
import { useCaseRecordSession } from '../hooks/useCaseRecordSession'
import { useRecordEditorCatalogs } from '../hooks/useRecordEditorCatalogs'
import { CASE_SUMMARY_CONFIRMATION_FIELD_PATH, getReviewPendingItems, REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'
import { useReviewWorkspaceShortcuts as useShortcuts } from '../hooks/useReviewWorkspaceShortcuts'
import { projectEvidenceDerivedContent } from '@biji/shared/utils'
import { CaseStatusBadge } from '../components/CaseStatusBadge'
import { SourceReselectionPanel } from '../components/SourceReselectionPanel'
import { ArchiveDecisionPanel } from '../components/ArchiveDecisionPanel'
import { ArchiveCompletionPanel, getArchiveCompletionGuidance } from '../components/ArchiveCompletionPanel'
import { useGuidedReviewCards } from '../hooks/useGuidedReviewCards'
import { GuidedReviewView } from '../components/GuidedReviewView'
import { GuidedReviewCard, QUICK_EVIDENCE_BATCH_GUIDANCE } from '../components/GuidedReviewCard'
import ImageUploader, { PHOTO_UPLOAD_GUIDANCE } from '../components/ImageUploader'

export default function CaseRecordGeneratePage() {
  const { caseId = '' } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const session = useCaseRecordSession(caseId)
  const photoNavigationBlocker = useBlocker(session.photoAssets.navigationUnsafe)
  const catalogs = useRecordEditorCatalogs()
  const [archiveDecisionBusy, setArchiveDecisionBusy] = useState(false)
  const [quickEvidenceGuidanceKey, setQuickEvidenceGuidanceKey] = useState<string | null>(null)
  const archiveDecisionInFlight = useRef(false)
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
    photoState: session.photoAssets.assetError ? 'error'
        : session.photoAssets.uploading ? 'uploading' : 'ready',
  })
  const currentGuidedAction = guidedReview.currentAction
  const currentGuidedActionKey = `${caseId}\u0000${currentGuidedAction?.id || ''}`
  const handleEvidenceBatchModeChange = useCallback((active: boolean) => {
    setQuickEvidenceGuidanceKey(active ? currentGuidedActionKey : null)
  }, [currentGuidedActionKey])
  const updateReport = useCallback((path: string, value: unknown) => {
    session.updateReport(path, value)
  }, [session.editingEnabled, session.updateReport])
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
    const sourceInvalid = Boolean(session.detail?.source.requires_reselection
      || ['invalid', 'requires_reselection'].includes(session.detail?.source.access_status || 'pending'))
    if (sourceInvalid) { message.warning('当前报告来源不可用，请重新选择后再设置压缩时机。'); return }
    if (decision === 'immediate' && !window.confirm(
      '压缩将直接读取源报告目录。\n\n压缩期间请勿修改、移动或删除源文件，也不要继续使用取证软件向该目录写入数据。\n\n请确认报告已生成完成并开始压缩。',
    )) return
    archiveDecisionInFlight.current = true
    setArchiveDecisionBusy(true)
    try {
      const saved = await session.autosave.saveNow()
      if (!saved) {
        message.warning('当前输入尚未保存成功，请先完成保存后再设置压缩时机。')
        return
      }
      const result = await session.decideArchive(decision)
      if (result.archive_task) message.success('归档任务已进入后台队列，可在案件卡片查看状态。')
      if (decision === 'deferred') message.success('草稿已保存，压缩已设为稍后处理，可返回案件工作台。')
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
  const resolveArchiveMappingRevision = async (): Promise<number | null> => {
    if (session.photoAssets.navigationUnsafe && !await session.photoAssets.waitForIdle()) {
      message.warning('图片尚未成功保存到案件草稿，请完成保存后再提交介质编号。')
      return null
    }
    const saved = await session.autosave.saveNow()
    if (!saved) {
      message.warning('当前输入尚未保存成功，请先完成保存后再提交介质编号。')
      return null
    }
    const latestDetail = await session.reloadDetail(caseId, { background: true })
    if (!latestDetail) {
      message.warning('案件最新版本读取失败，请稍后重试。')
      return null
    }
    return latestDetail.shell.revision
  }
  useShortcuts({ onSave: saveNow, previewOpen: false, onClosePreview: () => undefined, enabled: Boolean(session.report) })
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
  const leaseMessage = session.lease.phase === 'read_only' ? '该案件当前由其他页面占用，当前页面为只读。'
    : session.lease.phase === 'expired' || session.leaseLost ? '编辑租约已失效，已停止自动保存。请重新获取租约后继续。'
      : session.lease.phase === 'failed' ? '编辑权限获取失败，请重新获取后继续。'
        : session.lease.phase === 'acquiring' ? '正在获取编辑租约，请稍候。' : null
  let guidedSpecialContent: React.ReactNode
  let guidedAssistantMessage: { title: string; description?: React.ReactNode } | undefined
  if (currentGuidedAction?.kind === 'save_recovery') {
    const saveState = session.autosave.draftState.status
    guidedAssistantMessage = {
      title: saveState === 'failed' ? '草稿保存失败'
        : saveState === 'conflict' ? '草稿保存发生冲突' : '正在重新保存当前输入',
      description: saveState === 'conflict'
        ? '当前输入仍保留在本页面。可以重试保存，或确认后加载服务端版本。'
        : saveState === 'failed' ? '当前输入仍保留在本页面，请重试保存。'
          : '保存完成前，当前输入会继续保留在本页面。',
    }
    if (saveState !== 'saving') guidedSpecialContent = <Space wrap>
        <Button type="primary" onClick={() => { void retryDraftSave() }}>重试保存</Button>
        {saveState === 'conflict' && <Button onClick={() => { void loadServerDraft() }}>加载服务端版本</Button>}
      </Space>
  } else if (currentGuidedAction?.kind === 'source_recovery') {
    guidedSpecialContent = <SourceReselectionPanel required controlsOnly onReselect={session.replaceSource} />
  } else if (currentGuidedAction?.kind === 'lease_recovery') {
    guidedAssistantMessage = {
      title: currentGuidedAction.title,
      description: leaseMessage || '当前页面没有有效编辑权限。',
    }
    guidedSpecialContent = session.lease.phase === 'read_only'
        ? <Button onClick={forceTakeover}>强制接管</Button>
        : session.lease.phase === 'acquiring' ? undefined
          : <Button onClick={reacquireLease}>重新获取编辑权限</Button>
  } else if (currentGuidedAction?.kind === 'photo_recovery') {
    guidedAssistantMessage = {
      title: currentGuidedAction.title,
      description: session.photoAssets.assetError || currentGuidedAction.description,
    }
    guidedSpecialContent = <ImageUploader materials={session.report.introduction.evidence_list || []}
      photos={session.photoAssets.files} onChange={session.photoAssets.handleChange} showGuidance={false} />
  } else if (currentGuidedAction?.kind === 'archive_decision') {
    guidedSpecialContent = <ArchiveDecisionPanel lifecycle={session.detail.shell.lifecycle} busy={archiveDecisionBusy}
      controlsOnly onImmediate={() => { void chooseArchive('immediate') }} onDeferred={() => { void chooseArchive('deferred') }} />
  } else if (currentGuidedAction?.pendingItem?.targetId === REVIEW_TARGET_IDS.evidenceCompleteness
    && quickEvidenceGuidanceKey === currentGuidedActionKey) {
    guidedAssistantMessage = {
      title: '快捷批量添加检材',
      description: <span id="quick-evidence-format-help">{QUICK_EVIDENCE_BATCH_GUIDANCE}</span>,
    }
  } else if (currentGuidedAction?.pendingItem?.targetId === REVIEW_TARGET_IDS.photos) {
    guidedAssistantMessage = {
      title: currentGuidedAction.title,
      description: [
        currentGuidedAction.description,
        PHOTO_UPLOAD_GUIDANCE,
        session.photoAssets.assetError,
      ].filter(Boolean).join(' '),
    }
    guidedSpecialContent = <ImageUploader materials={session.report.introduction.evidence_list || []}
      photos={session.photoAssets.files} onChange={session.photoAssets.handleChange} showGuidance={false} />
  } else if (currentGuidedAction?.pendingItem?.targetId === REVIEW_TARGET_IDS.discNumber) {
    guidedAssistantMessage = getArchiveCompletionGuidance(
      session.detail.shell.lifecycle,
      session.completedArchive.result?.parts ?? null,
      archiveMedium,
    )
    guidedSpecialContent = <ArchiveCompletionPanel lifecycle={session.detail.shell.lifecycle} caseId={caseId}
      parts={session.completedArchive.result?.parts ?? null}
      planRowRevision={session.completedArchive.result?.plan_row_revision ?? null}
      archiveMedium={archiveMedium}
      firstDiscNumber={session.report.attachments?.disc_number || ''}
      onFirstDiscNumberChange={value => updateReport('attachments.disc_number', value)}
      resolveExpectedRevision={resolveArchiveMappingRevision}
      readOnly={!session.editingEnabled} controlsOnly
      onCompleted={() => {
        session.completedArchive.reload()
        void session.reloadDetail(caseId)
      }} />
  } else if (currentGuidedAction?.kind === 'ready') {
    guidedSpecialContent = <Button type="primary" size="large" icon={<SaveOutlined />}
      loading={session.autosave.draftState.status === 'saving' || session.photoAssets.navigationUnsafe}
      disabled={!session.editingEnabled}
      onClick={() => { void handleBackToWorkbench() }}>保存并退出</Button>
  }
  const guidedInteractionDisabled = !session.editingEnabled
  const confirmCurrentGuidedField = () => {
    const targetId = currentGuidedAction?.pendingItem?.targetId
    if (targetId === REVIEW_TARGET_IDS.caseSummary) {
      session.setCaseSummaryConfirmed(true)
    }
    if (targetId === REVIEW_TARGET_IDS.evidenceCompleteness) {
      session.setEvidenceCompletenessConfirmed(true)
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
    <div className="review-page review-page--guided">
      {currentGuidedAction ? (
        <GuidedReviewView conversationKey={caseId} history={guidedReview.history}
          previouslyHandledFields={guidedReview.previouslyHandledFields} currentAction={currentGuidedAction}
          allActions={guidedReview.allActions} systemStatus={guidedReview.systemStatus}
          hasResponse={Boolean(guidedSpecialContent || currentGuidedAction.pendingItem)}
          assistantMessage={guidedAssistantMessage}
          onSelectAction={guidedReview.selectAction}
          onRevisitAction={guidedReview.revisitAction}
          onRevisitHandledField={guidedReview.revisitHandledField}
          evidenceItems={session.report.introduction.evidence_list || []}
          onEvidenceItemsChange={(items, options) => {
            updateReport('introduction.evidence_list', items)
            if (options?.affectsCompleteness !== false) session.setEvidenceCompletenessConfirmed(false)
          }}
          evidenceReadOnly={guidedInteractionDisabled}
          evidenceSaveState={session.autosave.draftState.status}
          evidenceSaveHasPending={session.autosave.hasPending}
          onConfirmCurrentAction={confirmCurrentGuidedAction}
          confirmCurrentActionDisabled={guidedInteractionDisabled}
          canReturnToPrevious={guidedReview.canReturnToPrevious}
          canReturnToNext={guidedReview.canReturnToNext}
          onReturnToPreviousAction={guidedReview.returnToPreviousAction}
          onReturnToNextAction={returnToNextGuidedAction}
          onStartArchiveNow={() => { void chooseArchive('immediate') }}
          startArchiveNowBusy={archiveDecisionBusy}
          onBackToWorkbench={() => { void handleBackToWorkbench() }}>
          <GuidedReviewCard action={currentGuidedAction} report={projectedReport || session.report}
            updateReport={updateReport} readOnly={guidedInteractionDisabled}
            specialContent={guidedSpecialContent}
            fieldStates={session.draft?.field_states}
            availableInspectors={catalogs.inspectors}
            inspectorLoading={catalogs.inspectorLoading}
            inspectorError={catalogs.inspectorError}
            onEvidenceCompletenessChange={session.setEvidenceCompletenessConfirmed}
            onEvidenceBatchModeChange={handleEvidenceBatchModeChange} />
        </GuidedReviewView>
      ) : null}
    </div>
  )
}
