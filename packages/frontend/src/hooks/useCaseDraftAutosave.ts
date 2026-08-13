// Layer 10: FE_Hooks — debounced revision-checked draft persistence.
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS, CASE_DRAFT_AUTOSAVE_DEBOUNCE_MS } from '@biji/shared/constants'
import type { CaseDraft, ClientIdentity, SaveStatus, SharedDefaultsSaveStatus } from '@biji/shared/types'
export type AutosaveStatus = 'idle' | 'saving' | 'saved' | 'failed' | 'conflict' | 'not_changed'

export interface AutosaveViewState {
  status: AutosaveStatus
  revision?: number
  errorCode?: string
}
interface Options {
  caseId: string
  draft: CaseDraft | null
  identity: ClientIdentity | null
  sharedDefaultsPatch?: Record<string, unknown> | null
  /** @deprecated compatibility alias; callers must provide a sparse object. */
  sharedValues?: Record<string, unknown> | null
  sharedDefaultsRevision: number | null
  includeSharedDefaults: boolean
  changeToken: number
  enabled: boolean
  leaseId?: string | null
  leaseToken?: string | null
  onSaved: (draft: CaseDraft, sharedStatus: SharedDefaultsSaveStatus, meta: AutosaveSaveMeta) => void
}
export interface AutosaveSaveMeta {
  hasNewerChanges: boolean
  savedThroughChangeToken: number
  sharedDefaultsPatch: Record<string, unknown> | null
}
interface SaveResponse {
  draft_save_status: SaveStatus
  shared_defaults_save_status: SharedDefaultsSaveStatus
  draft: CaseDraft | null
}
function errorCode(error: any): string {
  const detail = error?.response?.data?.detail
  return typeof detail?.code === 'string' ? detail.code : 'DRAFT_SAVE_FAILED'
}
function conflictResult(error: any): SaveResponse | null {
  const result = error?.response?.data?.detail?.data
  return result && typeof result === 'object' ? result as SaveResponse : null
}
function cloneDraft(draft: CaseDraft): CaseDraft {
  return JSON.parse(JSON.stringify(draft)) as CaseDraft
}
function saveSignature(
  draft: CaseDraft,
  sharedDefaultsPatch: Record<string, unknown> | null,
  sharedDefaultsRevision: number | null,
): string {
  const cloned = cloneDraft(draft)
  const { lifecycle: _lifecycle, revision: _revision, updated_at: _updatedAt, ...editable } = cloned
  return JSON.stringify({ draft: editable, sharedDefaultsPatch, sharedDefaultsRevision })
}
export function useCaseDraftAutosave(options: Options) {
  const {
    caseId, draft, identity, sharedDefaultsPatch, sharedValues, sharedDefaultsRevision,
    includeSharedDefaults, changeToken, enabled, leaseId, leaseToken, onSaved,
  } = options
  const latest = useRef({ draft, identity, sharedDefaultsPatch: sharedDefaultsPatch ?? sharedValues, sharedDefaultsRevision, includeSharedDefaults, changeToken, leaseId, leaseToken })
  const pending = useRef<CaseDraft | null>(null)
  const onSavedRef = useRef(onSaved)
  const timer = useRef<number | null>(null)
  const sequence = useRef(0)
  const inFlight = useRef<Promise<boolean> | null>(null)
  const inFlightToken = useRef<number | null>(null)
  const rerunAfterFlight = useRef(false)
  const flushRequested = useRef(false)
  const lastSavedSignature = useRef<string | null>(null)
  const lastSavedDraft = useRef<CaseDraft | null>(changeToken === 0 ? draft : null)
  const sendRef = useRef<((snapshot?: CaseDraft) => Promise<boolean>) | null>(null)
  const [draftState, setDraftState] = useState<AutosaveViewState>({ status: 'idle' })
  const [sharedState, setSharedState] = useState<AutosaveViewState>({ status: 'not_changed' })
  const [hasPending, setHasPending] = useState(false)
  latest.current = { draft, identity, sharedDefaultsPatch: sharedDefaultsPatch ?? sharedValues, sharedDefaultsRevision, includeSharedDefaults, changeToken, leaseId, leaseToken }
  if (changeToken === 0 && !pending.current && !inFlight.current) lastSavedDraft.current = draft
  onSavedRef.current = onSaved
  const clearTimer = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
  }, [])

  const performSend = useCallback(async (snapshot?: CaseDraft) => {
    const current = latest.current
    const value = snapshot || pending.current || current.draft
    if (!enabled || !value || !current.identity) return false
    const requestId = ++sequence.current
    const requestChangeToken = current.changeToken
    const includeDefaults = current.includeSharedDefaults && current.sharedDefaultsPatch && Object.keys(current.sharedDefaultsPatch).length > 0 && current.sharedDefaultsRevision !== null
    const requestSharedPatch = includeDefaults ? { ...current.sharedDefaultsPatch } : null
    const requestSignature = saveSignature(value, requestSharedPatch, includeDefaults ? current.sharedDefaultsRevision : null)
    if (!snapshot && pending.current && requestSignature === lastSavedSignature.current) {
      pending.current = null
      setHasPending(false)
      setDraftState({ status: 'saved', revision: value.revision })
      lastSavedDraft.current = cloneDraft(value)
      return true
    }
    setDraftState({ status: 'saving' })
    setSharedState(includeDefaults ? { status: 'saving' } : { status: 'not_changed' })
    const controller = new AbortController()
    try {
      const response = await axios.patch<{ data: SaveResponse }>(
        API_ENDPOINTS.WORKBENCH_DRAFT(caseId),
        {
          draft: withoutLifecycle(cloneDraft(value)),
          expected_revision: value.revision,
          shared_defaults_patch: requestSharedPatch,
          shared_defaults_revision: includeDefaults ? current.sharedDefaultsRevision : null,
          identity: current.identity,
          lease_id: current.leaseId || null,
          lease_token: current.leaseToken || null,
        },
        { signal: controller.signal },
      )
      if (requestId !== sequence.current) return true
      const result = response.data.data
      const sharedStatus = result.shared_defaults_save_status
      const draftStatus = result.draft_save_status
      if (draftStatus.status !== 'saved' || !result.draft) {
        setDraftState({ status: draftStatus.status === 'conflict' ? 'conflict' : 'failed', revision: draftStatus.revision, errorCode: draftStatus.error_code })
        setSharedState(includeDefaults ? { status: toAutosaveStatus(sharedStatus.status), revision: sharedStatus.revision, errorCode: sharedStatus.error_code } : { status: 'not_changed' })
        pending.current = value
        setHasPending(true)
        return false
      }
      setDraftState({ status: 'saved', revision: result.draft_save_status.revision })
      lastSavedDraft.current = cloneDraft(result.draft)
      setSharedState(includeDefaults ? { status: toAutosaveStatus(sharedStatus.status), revision: sharedStatus.revision, errorCode: sharedStatus.error_code } : { status: 'not_changed' })
      lastSavedSignature.current = requestSignature
      const hasNewerChanges = latest.current.changeToken > requestChangeToken
      if (hasNewerChanges && pending.current) {
        pending.current = {
          ...pending.current,
          revision: result.draft.revision,
          updated_at: result.draft.updated_at,
        }
        rerunAfterFlight.current = true
      } else pending.current = null
      setHasPending(hasNewerChanges)
      onSavedRef.current(result.draft, sharedStatus, {
        hasNewerChanges, savedThroughChangeToken: requestChangeToken,
        sharedDefaultsPatch: requestSharedPatch,
      })
      return true
    } catch (error) {
      if (requestId !== sequence.current) return true
      const conflict = conflictResult(error)
      if (conflict?.draft_save_status?.status === 'conflict') {
        setDraftState({ status: 'conflict', errorCode: conflict.draft_save_status.error_code })
        setSharedState({
          status: toAutosaveStatus(conflict.shared_defaults_save_status?.status),
          errorCode: conflict.shared_defaults_save_status?.error_code,
        })
      } else {
        setDraftState({ status: 'failed', errorCode: errorCode(error) })
        setSharedState(includeDefaults ? { status: 'failed', errorCode: errorCode(error) } : { status: 'not_changed' })
      }
      setHasPending(true)
      pending.current = value
      return false
    } finally {
      controller.abort()
    }
  }, [caseId, enabled])

  const send = useCallback((snapshot?: CaseDraft): Promise<boolean> => {
    if (inFlight.current) {
      if (inFlightToken.current !== null && latest.current.changeToken > inFlightToken.current) {
        rerunAfterFlight.current = true
      }
      return inFlight.current
    }
    inFlightToken.current = latest.current.changeToken
    const request = performSend(snapshot)
    inFlight.current = request
    void request.then(success => {
      if (inFlight.current === request) inFlight.current = null
      inFlightToken.current = null
      const rerun = success && rerunAfterFlight.current && pending.current !== null
      rerunAfterFlight.current = false
      if (rerun && !flushRequested.current) {
        clearTimer()
        window.setTimeout(() => { void sendRef.current?.() }, 0)
      }
    })
    return request
  }, [clearTimer, performSend])
  sendRef.current = send

  useEffect(() => {
    if (!enabled || changeToken <= 0 || !draft) return undefined
    pending.current = cloneDraft(draft)
    setHasPending(true)
    setDraftState({ status: 'saving', revision: draft.revision })
    if (latest.current.includeSharedDefaults) setSharedState({ status: 'saving' })
    clearTimer()
    timer.current = window.setTimeout(() => { void send() }, CASE_DRAFT_AUTOSAVE_DEBOUNCE_MS)
    return clearTimer
  }, [changeToken, clearTimer, enabled, send])

  useEffect(() => () => {
    clearTimer()
    sequence.current += 1
  }, [clearTimer])

  const saveNow = useCallback(() => {
    clearTimer()
    if (!pending.current && changeToken > 0 && draft) pending.current = cloneDraft(draft)
    if (!pending.current && !inFlight.current) return Promise.resolve(true)
    flushRequested.current = true
    const flush = async () => {
      try {
        let success = true
        while (pending.current || inFlight.current) {
          success = await send()
          if (!success) return false
        }
        return true
      } finally {
        flushRequested.current = false
      }
    }
    return flush()
  }, [changeToken, clearTimer, draft, send])

  const retry = useCallback(() => send(), [send])

  const rebase = useCallback((rebasedDraft: CaseDraft, keepPending: boolean) => {
    clearTimer()
    sequence.current += 1
    flushRequested.current = false
    lastSavedSignature.current = null
    if (!keepPending) {
      pending.current = null
      rerunAfterFlight.current = false
      lastSavedDraft.current = cloneDraft(rebasedDraft)
      setHasPending(false)
      setDraftState({ status: 'saved', revision: rebasedDraft.revision })
      return
    }
    pending.current = cloneDraft(rebasedDraft)
    rerunAfterFlight.current = inFlight.current !== null
    setHasPending(true)
    setDraftState({ status: 'saving', revision: rebasedDraft.revision })
    if (!inFlight.current) window.setTimeout(() => { void sendRef.current?.() }, 0)
  }, [clearTimer])

  const reset = useCallback(() => {
    clearTimer()
    sequence.current += 1
    rerunAfterFlight.current = false
    pending.current = null
    lastSavedSignature.current = null
    lastSavedDraft.current = null
    setHasPending(false)
    setDraftState({ status: 'idle' })
    setSharedState({ status: 'not_changed' })
  }, [clearTimer])

  const getLastSavedDraft = useCallback(() => (
    lastSavedDraft.current ? cloneDraft(lastSavedDraft.current) : null
  ), [])

  return { draftState, sharedState, hasPending, saveNow, retry, rebase, reset, getLastSavedDraft }
}

function toAutosaveStatus(status: SharedDefaultsSaveStatus['status'] | 'saved' | 'conflict' | 'not_changed' | undefined): AutosaveStatus {
  if (status === 'updated' || status === 'saved') return 'saved'
  if (status === 'revision_conflict' || status === 'conflict') return 'conflict'
  if (status === 'failed') return 'failed'
  return 'not_changed'
}

function withoutLifecycle(draft: CaseDraft): Omit<CaseDraft, 'lifecycle'> {
  const { lifecycle: _lifecycle, ...editable } = draft
  return editable
}
