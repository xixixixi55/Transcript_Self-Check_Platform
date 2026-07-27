// Layer 10: FE_Hooks — debounced revision-checked draft persistence.
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS, CASE_DRAFT_AUTOSAVE_DEBOUNCE_MS } from '@biji/shared/constants'
import type { CaseDraft, ClientIdentity, SaveStatus } from '@biji/shared/types'

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
  sharedValues: Record<string, unknown> | null
  sharedDefaultsRevision: number | null
  includeSharedDefaults: boolean
  changeToken: number
  enabled: boolean
  leaseId?: string | null
  leaseToken?: string | null
  onSaved: (draft: CaseDraft, sharedStatus: SaveStatus) => void
}

interface SaveResponse {
  draft_save_status: SaveStatus
  shared_defaults_save_status: SaveStatus
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

export function useCaseDraftAutosave(options: Options) {
  const {
    caseId, draft, identity, sharedValues, sharedDefaultsRevision,
    includeSharedDefaults, changeToken, enabled, leaseId, leaseToken, onSaved,
  } = options
  const latest = useRef({ draft, identity, sharedValues, sharedDefaultsRevision, includeSharedDefaults, leaseId, leaseToken })
  const pending = useRef<CaseDraft | null>(null)
  const timer = useRef<number | null>(null)
  const sequence = useRef(0)
  const [draftState, setDraftState] = useState<AutosaveViewState>({ status: 'idle' })
  const [sharedState, setSharedState] = useState<AutosaveViewState>({ status: 'not_changed' })
  const [hasPending, setHasPending] = useState(false)

  latest.current = { draft, identity, sharedValues, sharedDefaultsRevision, includeSharedDefaults, leaseId, leaseToken }

  const clearTimer = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
  }, [])

  const send = useCallback(async (snapshot?: CaseDraft) => {
    const current = latest.current
    const value = snapshot || pending.current || current.draft
    if (!enabled || !value || !current.identity) return false
    const requestId = ++sequence.current
    const includeDefaults = current.includeSharedDefaults && current.sharedValues && current.sharedDefaultsRevision !== null
    setDraftState({ status: 'saving' })
    setSharedState(includeDefaults ? { status: 'saving' } : { status: 'not_changed' })
    const controller = new AbortController()
    try {
      const response = await axios.patch<{ data: SaveResponse }>(
        API_ENDPOINTS.WORKBENCH_DRAFT(caseId),
        {
          draft: cloneDraft(value),
          expected_revision: value.revision,
          shared_defaults: includeDefaults ? current.sharedValues : null,
          shared_defaults_revision: includeDefaults ? current.sharedDefaultsRevision : null,
          identity: current.identity,
          lease_id: current.leaseId || null,
          lease_token: current.leaseToken || null,
        },
        { signal: controller.signal },
      )
      if (requestId !== sequence.current) return false
      const result = response.data.data
      const sharedStatus = result.shared_defaults_save_status
      const fullySaved = result.draft_save_status.status === 'saved'
        && (!includeDefaults || sharedStatus.status === 'saved')
      setDraftState({ status: 'saved', revision: result.draft_save_status.revision })
      setSharedState(includeDefaults
        ? { status: sharedStatus.status, revision: sharedStatus.revision, errorCode: sharedStatus.error_code }
        : { status: 'not_changed' })
      setHasPending(!fullySaved)
      if (result.draft) {
        pending.current = fullySaved ? null : value
        onSaved(result.draft, sharedStatus)
      }
      return true
    } catch (error) {
      if (requestId !== sequence.current) return false
      const conflict = conflictResult(error)
      if (conflict?.draft_save_status?.status === 'conflict') {
        setDraftState({ status: 'conflict', errorCode: conflict.draft_save_status.error_code })
        setSharedState({
          status: conflict.shared_defaults_save_status?.status || 'not_changed',
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
  }, [caseId, enabled, onSaved])

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
    if (draft) pending.current = cloneDraft(draft)
    return send()
  }, [clearTimer, draft, send])

  const retry = useCallback(() => send(), [send])

  const reset = useCallback(() => {
    clearTimer()
    pending.current = null
    setHasPending(false)
    setDraftState({ status: 'idle' })
    setSharedState({ status: 'not_changed' })
  }, [clearTimer])

  return { draftState, sharedState, hasPending, saveNow, retry, reset }
}
