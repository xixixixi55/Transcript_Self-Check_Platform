// 第 10 层：FE_Hooks — 协调案件编辑会话、持久化、来源与租约。
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS, CASE_TASK_POLL_INTERVAL_MS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import { applyReportEdit, buildMaterialPhotoGroups } from '@biji/shared/utils'
import type { ArchiveDecision, ArchiveDecisionResult, CaseDraft, CasePhotoBindingResult, ClientIdentity, FieldConfirmation, FieldState, InspectionReport, OpaqueAssetRef, SharedDefaults, SharedDefaultsSaveStatus } from '@biji/shared/types'
import { useCaseDraftAutosave } from './useCaseDraftAutosave'
import type { AutosaveSaveMeta } from './useCaseDraftAutosave'
import { useCasePhotoAssets } from './useCasePhotoAssets'
import { useCaseWorkbench } from './useCaseWorkbench'
import { createClientIdentity, useEditLease } from './useEditLease'
import { useTaskRecords } from './useTaskRecords'
import { shouldHydrateServerDraft } from './useCaseDraftHydration'
import { useCompletedArchiveResult } from './useCompletedArchiveResult'
import { buildSourceReplacementRequest } from './useSourceAuthorizationRequests'
import { EVIDENCE_COMPLETENESS_FIELD_PATH } from './useReviewChecklist'

const ACTIVE_ARCHIVE_LIFECYCLES = new Set(['archive_queued', 'archiving'])

export function reportWithPhotoAssetRefs(
  report: InspectionReport,
  refs: OpaqueAssetRef[],
): InspectionReport {
  const photoIds = refs.map(ref => ref.asset_id)
  const attachments = report.attachments || {
    extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '',
  }
  return {
    ...report,
    attachments: {
      ...attachments,
      photo_ids: photoIds,
      photo_groups: buildMaterialPhotoGroups(report, photoIds),
    },
  }
}

export function useCaseRecordSession(caseId: string) {
  const workbench = useCaseWorkbench(caseId)
  const [draft, setDraft] = useState<CaseDraft | null>(null)
  const [report, setReport] = useState<InspectionReport | null>(null)
  const [defaults, setDefaults] = useState<SharedDefaults | null>(null)
  const [identity, setIdentity] = useState<ClientIdentity | null>(null)
  const [changeToken, setChangeToken] = useState(0)
  const [leaseLost, setLeaseLost] = useState(false)
  const terminalStatus = useRef<string | null>(null)
  const lastHydratedDraftKey = useRef<string | null>(null)
  const changeTokenRef = useRef(0)
  const localReportEdits = useRef<Array<{ path: string; value: unknown; token: number }>>([])
  const localFieldStateEdits = useRef<Array<{ fieldPath: string; state: FieldState; token: number }>>([])
  const handleLeaseLost = useCallback(() => setLeaseLost(true), [])

  useEffect(() => {
    let active = true
    axios.get<{ data: SharedDefaults }>(API_ENDPOINTS.WORKBENCH_DEFAULTS).then(response => {
      if (!active) return
      const value = response.data.data
      setDefaults(value)
      setIdentity(createClientIdentity(value.deployment_instance_id))
    }).catch(() => { if (active) setDefaults(null) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    lastHydratedDraftKey.current = null
    setDraft(null)
    setReport(null)
    setChangeToken(0)
    changeTokenRef.current = 0
    setLeaseLost(false)
    localReportEdits.current = []
    localFieldStateEdits.current = []
  }, [caseId])

  const serverDraft = workbench.detail?.draft
  useEffect(() => {
    if (!serverDraft || !shouldHydrateServerDraft(caseId, serverDraft, lastHydratedDraftKey.current, changeToken)) return
    lastHydratedDraftKey.current = `${caseId}:${serverDraft.revision}`
    setDraft(serverDraft)
    setReport(JSON.parse(JSON.stringify(serverDraft.report)) as InspectionReport)
    setChangeToken(0)
    changeTokenRef.current = 0
    setLeaseLost(false)
  }, [caseId, changeToken, serverDraft?.case_id, serverDraft?.revision])

  const taskIds = workbench.detail ? [workbench.detail.parse_task.task_id] : []
  const { records: taskRecords } = useTaskRecords(taskIds)
  const parseTask = workbench.detail ? taskRecords[workbench.detail.parse_task.task_id] || workbench.detail.parse_task : null

  useEffect(() => {
    if (workbench.detail?.draft || !parseTask || !['succeeded', 'failed_retryable', 'interrupted'].includes(parseTask.status)) return
    if (terminalStatus.current === parseTask.status) return
    terminalStatus.current = parseTask.status
    void workbench.reloadDetail(caseId)
  }, [caseId, parseTask, workbench.detail?.draft, workbench.reloadDetail])

  useEffect(() => {
    if (workbench.detail?.source.access_status !== 'pending') return
    const timer = window.setInterval(() => { void workbench.reloadDetail(caseId, { background: true }) }, 1500)
    return () => window.clearInterval(timer)
  }, [caseId, workbench.detail?.source.access_status, workbench.reloadDetail])

  const archiveLifecycle = workbench.detail?.shell.lifecycle
  const completedArchive = useCompletedArchiveResult(
    workbench.detail?.shell.archive_task_summary, workbench.archiveResult,
  )
  useEffect(() => {
    if (!archiveLifecycle || !ACTIVE_ARCHIVE_LIFECYCLES.has(archiveLifecycle)) return
    const timer = window.setInterval(() => {
      void workbench.reloadDetail(caseId, { background: true })
    }, CASE_TASK_POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [archiveLifecycle, caseId, workbench.reloadDetail])

  const lease = useEditLease({
    caseId,
    identity,
    enabled: Boolean(draft),
    onLeaseLost: handleLeaseLost,
  })
  const editingEnabled = lease.phase === 'active' && !leaseLost
  const draftForSave = useMemo(() => draft && report ? { ...draft, report } : draft, [draft, report])
  const onSaved = useCallback((savedDraft: CaseDraft, _sharedStatus: SharedDefaultsSaveStatus, meta: AutosaveSaveMeta) => {
    localReportEdits.current = localReportEdits.current.filter(
      edit => edit.token > meta.savedThroughChangeToken,
    )
    lastHydratedDraftKey.current = `${caseId}:${savedDraft.revision}`
    localFieldStateEdits.current = localFieldStateEdits.current.filter(
      edit => edit.token > meta.savedThroughChangeToken,
    )
    const rebasedFieldStates = localFieldStateEdits.current.reduce((states, edit) => ({
      ...states,
      [edit.fieldPath]: edit.state,
    }), savedDraft.field_states)
    setDraft(localFieldStateEdits.current.length > 0
      ? { ...savedDraft, field_states: rebasedFieldStates }
      : savedDraft)
    if (!meta.hasNewerChanges) changeTokenRef.current = 0
    setChangeToken(current => meta.hasNewerChanges ? current : 0)
    if (!meta.hasNewerChanges) setReport(JSON.parse(JSON.stringify(savedDraft.report)) as InspectionReport)
  }, [caseId])
  const autosave = useCaseDraftAutosave({
    caseId, draft: draftForSave, identity, sharedDefaultsPatch: null,
    sharedDefaultsRevision: null, includeSharedDefaults: false,
    changeToken, enabled: editingEnabled, leaseId: lease.lease?.lease_id,
    leaseToken: lease.lease?.lease_token, onSaved,
  })

  const updateReport = useCallback((path: string, value: unknown) => {
    if (!editingEnabled) return
    setReport(current => {
      if (!current) return current
      return applyReportEdit(current, path, value)
    })
    const token = changeTokenRef.current + 1
    changeTokenRef.current = token
    localReportEdits.current.push({ path, value, token })
    setChangeToken(token)
  }, [editingEnabled])

  const setEvidenceCompletenessConfirmed = useCallback((confirmed: boolean) => {
    if (!editingEnabled) return
    const token = changeTokenRef.current + 1
    changeTokenRef.current = token
    setDraft(current => {
      if (!current) return current
      const previous = current.field_states[EVIDENCE_COMPLETENESS_FIELD_PATH]
      const confirmation: FieldConfirmation = confirmed ? 'confirmed' : 'pending'
      const state: FieldState = {
        field_path: EVIDENCE_COMPLETENESS_FIELD_PATH,
        source: 'user',
        confirmation,
        revision: (previous?.revision ?? 0) + 1,
        last_changed_at: new Date().toISOString(),
      }
      localFieldStateEdits.current.push({
        fieldPath: EVIDENCE_COMPLETENESS_FIELD_PATH,
        state,
        token,
      })
      return {
        ...current,
        field_states: { ...current.field_states, [EVIDENCE_COMPLETENESS_FIELD_PATH]: state },
      }
    })
    setChangeToken(token)
  }, [editingEnabled])

  const updatePhotoAssetRefs = useCallback(async (
    refs: OpaqueAssetRef[], expectedRefs: OpaqueAssetRef[],
  ): Promise<boolean> => {
    if (!editingEnabled || !lease.lease) return false
    const response = await axios.patch<{ data: CasePhotoBindingResult }>(
      API_ENDPOINTS.WORKBENCH_CASE_PHOTO_BINDING(caseId), {
        asset_refs: refs,
        expected_asset_ids: expectedRefs.map(ref => ref.asset_id),
        lease_id: lease.lease.lease_id,
        lease_token: lease.lease.lease_token,
      },
    )
    const savedDraft = response.data.data.draft
    let rebasedReport = savedDraft.report
    for (const edit of localReportEdits.current) {
      rebasedReport = applyReportEdit(rebasedReport, edit.path, edit.value)
    }
    rebasedReport = reportWithPhotoAssetRefs(rebasedReport, refs)
    const rebasedFieldStates = localFieldStateEdits.current.reduce((states, edit) => ({
      ...states,
      [edit.fieldPath]: edit.state,
    }), savedDraft.field_states)
    const rebasedDraft = {
      ...savedDraft,
      report: rebasedReport,
      field_states: rebasedFieldStates,
      asset_refs: refs,
    }
    setDraft(rebasedDraft)
    setReport(rebasedReport)
    lastHydratedDraftKey.current = `${caseId}:${savedDraft.revision}`
    autosave.rebase(rebasedDraft, localReportEdits.current.length > 0 || localFieldStateEdits.current.length > 0)
    return true
  }, [autosave, caseId, editingEnabled, lease.lease])

  const photoAssets = useCasePhotoAssets({
    caseId, assetRefs: draft?.asset_refs || [], draftRevision: draft?.revision,
    editingEnabled, lease: lease.lease,
    onAssetRefsChange: updatePhotoAssetRefs,
  })

  const replaceSource = useCallback(async (sourcePath: string) => {
    if (!workbench.detail?.source) return false
    await axios.post(API_ENDPOINTS.WORKBENCH_SOURCE(caseId), buildSourceReplacementRequest(
      sourcePath, workbench.detail.shell.revision,
    ))
    await workbench.reloadDetail(caseId)
    return true
  }, [caseId, workbench.detail?.source, workbench.reloadDetail])

  const retrySave = useCallback(() => autosave.retry(), [autosave])

  const decideArchive = useCallback(async (decision: ArchiveDecision) => {
    const latestDetail = await workbench.reloadDetail(caseId)
    if (!latestDetail) throw new Error('CASE_NOT_LOADED')
    const response = await axios.post<{ data: ArchiveDecisionResult }>(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_DECISION(caseId), {
        decision,
        expected_revision: latestDetail.shell.revision,
        identity,
      },
      { timeout: WORKBENCH_REQUEST_TIMEOUT_MS },
    )
    await workbench.reloadDetail(caseId)
    return response.data.data
  }, [caseId, identity, workbench.reloadDetail])

  const loadServerVersion = useCallback(async () => {
    await workbench.reloadDetail(caseId)
    autosave.reset()
  }, [autosave, caseId, workbench.reloadDetail])

  return {
    ...workbench, draft, report, defaults, identity, parseTask, taskRecords, lease, editingEnabled,
    leaseLost, autosave, retrySave,
    updateReport, setEvidenceCompletenessConfirmed, updatePhotoAssetRefs, photoAssets, replaceSource, decideArchive, loadServerVersion,
    completedArchive,
  }
}
