// Layer 10: FE_Hooks — case editor session, persistence, source and lease coordination.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import { applyReportEdit } from '@biji/shared/utils'
import type { ArchiveDecision, ArchiveDecisionResult, CaseDraft, ClientIdentity, InspectionReport, OpaqueAssetRef, SharedDefaults, SaveStatus } from '@biji/shared/types'
import { useCaseDraftAutosave } from './useCaseDraftAutosave'
import type { AutosaveViewState } from './useCaseDraftAutosave'
import { useCasePhotoAssets } from './useCasePhotoAssets'
import { useCaseWorkbench } from './useCaseWorkbench'
import { createClientIdentity, useEditLease } from './useEditLease'
import { useTaskRecords } from './useTaskRecords'

const SHARED_FIELD_PATHS = new Set([
  'document_number', 'introduction.inspection_place', 'inspection.method', 'inspection.hardware_device',
  'introduction.inspectors', 'introduction.inspector_snapshots',
])

function sharedValues(report: InspectionReport, prefix: string) {
  return {
    document_number: report.document_number || '',
    inspection_place: report.introduction?.inspection_place || '',
    inspection_method: report.inspection?.method || '',
    hardware_device: report.inspection?.hardware_device || '',
    inspector_order: (report.introduction?.inspectors || []).map(item => `${item.name}|${item.unit}|${item.badge_number}`),
    disc_number_prefix: prefix,
  }
}

export function useCaseRecordSession(caseId: string) {
  const workbench = useCaseWorkbench(caseId)
  const [draft, setDraft] = useState<CaseDraft | null>(null)
  const [report, setReport] = useState<InspectionReport | null>(null)
  const [defaults, setDefaults] = useState<SharedDefaults | null>(null)
  const [identity, setIdentity] = useState<ClientIdentity | null>(null)
  const [changeToken, setChangeToken] = useState(0)
  const [needsSharedDefaults, setNeedsSharedDefaults] = useState(false)
  const [sharedDefaultsSaveState, setSharedDefaultsSaveState] = useState<AutosaveViewState>({ status: 'not_changed' })
  const [leaseLost, setLeaseLost] = useState(false)
  const terminalStatus = useRef<string | null>(null)
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
    if (!workbench.detail?.draft) return
    setDraft(workbench.detail.draft)
    setReport(JSON.parse(JSON.stringify(workbench.detail.draft.report)) as InspectionReport)
    setChangeToken(0)
    setNeedsSharedDefaults(false)
    setLeaseLost(false)
  }, [workbench.detail?.draft])

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
    const timer = window.setInterval(() => { void workbench.reloadDetail(caseId) }, 1500)
    return () => window.clearInterval(timer)
  }, [caseId, workbench.detail?.source.access_status, workbench.reloadDetail])

  const lease = useEditLease({
    caseId,
    identity,
    enabled: Boolean(draft),
    onLeaseLost: handleLeaseLost,
  })
  const editingEnabled = lease.phase === 'active' && !leaseLost
  const draftForSave = useMemo(() => draft && report ? { ...draft, report } : draft, [draft, report])
  const valuesForDefaults = useMemo(() => report ? sharedValues(report, defaults?.disc_number_prefix || '') : null, [defaults?.disc_number_prefix, report])

  const onSaved = useCallback((savedDraft: CaseDraft, sharedStatus: SaveStatus) => {
    setDraft(savedDraft)
    if (sharedStatus.status === 'saved') {
      setNeedsSharedDefaults(false)
      setSharedDefaultsSaveState({ status: 'saved', revision: sharedStatus.revision })
    }
  }, [])
  const autosave = useCaseDraftAutosave({
    caseId, draft: draftForSave, identity, sharedValues: valuesForDefaults,
    sharedDefaultsRevision: defaults?.revision ?? null, includeSharedDefaults: needsSharedDefaults,
    changeToken, enabled: editingEnabled, leaseId: lease.lease?.lease_id,
    leaseToken: lease.lease?.lease_token, onSaved,
  })

  const updateReport = useCallback((path: string, value: unknown) => {
    if (!editingEnabled) return
    setReport(current => current ? applyReportEdit(current, path, value) : current)
    if (SHARED_FIELD_PATHS.has(path) || path.startsWith('introduction.inspectors') || path.startsWith('introduction.inspector_snapshots')) setNeedsSharedDefaults(true)
    setChangeToken(value => value + 1)
  }, [editingEnabled])

  const updatePhotoAssetRefs = useCallback((refs: OpaqueAssetRef[]) => {
    if (!editingEnabled) return false
    setDraft(current => current ? { ...current, asset_refs: refs } : current)
    setReport(current => {
      if (!current) return current
      const attachments = current.attachments || { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' }
      return {
        ...current,
        attachments: { ...attachments, photo_ids: refs.map(ref => ref.asset_id), photo_groups: undefined },
      }
    })
    setChangeToken(value => value + 1)
    return true
  }, [editingEnabled])

  const photoAssets = useCasePhotoAssets({
    caseId, assetRefs: draft?.asset_refs || [], editingEnabled, lease: lease.lease,
    onAssetRefsChange: updatePhotoAssetRefs,
  })

  const replaceSource = useCallback(async (sourcePath: string) => {
    if (!workbench.detail?.source) return false
    await axios.post(API_ENDPOINTS.WORKBENCH_SOURCE(caseId), {
      source_path: sourcePath,
      expected_revision: workbench.detail.shell.revision,
    })
    await workbench.reloadDetail(caseId)
    return true
  }, [caseId, workbench.detail?.source, workbench.reloadDetail])

  const saveSharedDefaults = useCallback(async (discNumberPrefix?: string) => {
    if (!defaults || !identity || !report) return false
    setSharedDefaultsSaveState({ status: 'saving' })
    try {
      const response = await axios.put<{ data: SharedDefaults }>(API_ENDPOINTS.WORKBENCH_DEFAULTS, {
        values: sharedValues(report, discNumberPrefix ?? defaults.disc_number_prefix),
        expected_revision: defaults.revision,
        identity,
      })
      const saved = response.data.data
      setDefaults(saved)
      setSharedDefaultsSaveState({ status: 'saved', revision: saved.revision })
      setNeedsSharedDefaults(false)
      return true
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      const code = typeof detail?.code === 'string' ? detail.code : 'SHARED_DEFAULTS_SAVE_FAILED'
      setSharedDefaultsSaveState({
        status: code === 'REVISION_CONFLICT' ? 'conflict' : 'failed',
        errorCode: code,
      })
      return false
    }
  }, [defaults, identity, report])

  const clearSharedDefaults = useCallback(async () => {
    if (!defaults || !identity) return false
    setSharedDefaultsSaveState({ status: 'saving' })
    try {
      const response = await axios.put<{ data: SharedDefaults }>(API_ENDPOINTS.WORKBENCH_DEFAULTS, {
        values: {
          document_number: '', inspection_place: '', inspection_method: '', hardware_device: '',
          inspector_order: [], disc_number_prefix: '',
        },
        expected_revision: defaults.revision,
        identity,
      })
      const saved = response.data.data
      setDefaults(saved)
      setSharedDefaultsSaveState({ status: 'saved', revision: saved.revision })
      return true
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      const code = typeof detail?.code === 'string' ? detail.code : 'SHARED_DEFAULTS_SAVE_FAILED'
      setSharedDefaultsSaveState({
        status: code === 'REVISION_CONFLICT' ? 'conflict' : 'failed',
        errorCode: code,
      })
      return false
    }
  }, [defaults, identity])

  const decideArchive = useCallback(async (decision: ArchiveDecision) => {
    if (!workbench.detail) throw new Error('CASE_NOT_LOADED')
    const response = await axios.post<{ data: ArchiveDecisionResult }>(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_DECISION(caseId), {
        decision,
        expected_revision: workbench.detail.shell.revision,
        identity,
      },
    )
    await workbench.reloadDetail(caseId)
    return response.data.data
  }, [caseId, identity, workbench.detail, workbench.reloadDetail])

  const loadServerVersion = useCallback(async () => {
    await workbench.reloadDetail(caseId)
    autosave.reset()
  }, [autosave, caseId, workbench.reloadDetail])

  return {
    ...workbench, draft, report, defaults, identity, parseTask, taskRecords, lease, editingEnabled,
    leaseLost, autosave, sharedDefaultsSaveState, saveSharedDefaults, clearSharedDefaults,
    updateReport, updatePhotoAssetRefs, photoAssets, replaceSource, decideArchive, loadServerVersion,
  }
}
