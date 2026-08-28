// 第 10 层：FE_Hooks — 单个活动编辑器租约，支持显式接管。
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS, EDIT_LEASE_HEARTBEAT_SECONDS } from '@biji/shared/constants'
import type { ClientIdentity, EditLease } from '@biji/shared/types'

export type LeasePhase = 'idle' | 'acquiring' | 'active' | 'read_only' | 'expired' | 'failed' | 'released'

interface Options {
  caseId?: string
  identity: ClientIdentity | null
  enabled: boolean
  onLeaseLost?: () => void
}
function getErrorCode(error: any): string {
  const detail = error?.response?.data?.detail
  return typeof detail?.code === 'string' ? detail.code : 'LEASE_REQUEST_FAILED'
}

export function createClientIdentity(deploymentInstanceId: string): ClientIdentity {
  const value = (key: string, prefix: string) => {
    try {
      const existing = window.sessionStorage.getItem(key)
      if (existing) return existing
      const generated = `${prefix}-${crypto.randomUUID()}`
      window.sessionStorage.setItem(key, generated)
      return generated
    } catch {
      return `${prefix}-${Math.random().toString(36).slice(2)}`
    }
  }
  return {
    client_instance_id: value('biji.workbench.client-instance', 'client'),
    session_id: value('biji.workbench.session', 'session'),
    deployment_instance_id: deploymentInstanceId,
    observed_at: new Date().toISOString(),
    identity_kind: 'local_session',
  }
}

export function useEditLease({ caseId, identity, enabled, onLeaseLost }: Options) {
  const [lease, setLease] = useState<EditLease | null>(null)
  const [phase, setPhase] = useState<LeasePhase>('idle')
  const [errorCode, setErrorCode] = useState<string | null>(null)
  const leaseRef = useRef<EditLease | null>(null)
  const heartbeatTimer = useRef<number | null>(null)
  const requestVersion = useRef(0)

  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimer.current !== null) window.clearInterval(heartbeatTimer.current)
    heartbeatTimer.current = null
  }, [])

  const releaseRequest = useCallback(async (value: EditLease | null) => {
    if (!value) return
    try {
      await axios.post(API_ENDPOINTS.WORKBENCH_LEASE_RELEASE(value.lease_id), {
        lease_token: value.lease_token, expected_revision: value.revision,
      })
    } catch {
      // 页面丢失时至少必须停止续租；到期时间仍以后端为准。
    }
  }, [])

  const heartbeat = useCallback(async () => {
    const value = leaseRef.current
    if (!value) return
    try {
      const response = await axios.post<{ data: EditLease }>(
        API_ENDPOINTS.WORKBENCH_LEASE_HEARTBEAT(value.lease_id), { lease_token: value.lease_token },
      )
      leaseRef.current = response.data.data
      setLease(response.data.data)
    } catch (error) {
      stopHeartbeat()
      leaseRef.current = null
      setLease(null)
      setPhase('expired')
      setErrorCode(getErrorCode(error))
      onLeaseLost?.()
    }
  }, [onLeaseLost, stopHeartbeat])

  const startHeartbeat = useCallback(() => {
    stopHeartbeat()
    heartbeatTimer.current = window.setInterval(() => { void heartbeat() }, EDIT_LEASE_HEARTBEAT_SECONDS * 1000)
  }, [heartbeat, stopHeartbeat])

  const acquire = useCallback(async (forceTakeover = false) => {
    if (!caseId || !identity || !enabled) return null
    const currentRequest = ++requestVersion.current
    stopHeartbeat()
    setPhase('acquiring')
    setErrorCode(null)
    try {
      const response = await axios.post<{ data: EditLease }>(API_ENDPOINTS.WORKBENCH_LEASE(caseId), {
        identity, force_takeover: forceTakeover,
      })
      if (currentRequest !== requestVersion.current) return null
      leaseRef.current = response.data.data
      setLease(response.data.data)
      setPhase('active')
      startHeartbeat()
      return response.data.data
    } catch (error) {
      if (currentRequest !== requestVersion.current) return null
      setLease(null)
      setPhase(getErrorCode(error) === 'LEASE_CONFLICT' || getErrorCode(error) === 'LEASE_TAKEOVER_REQUIRED' ? 'read_only' : 'failed')
      setErrorCode(getErrorCode(error))
      return null
    }
  }, [caseId, enabled, identity, startHeartbeat, stopHeartbeat])

  const release = useCallback(async () => {
    requestVersion.current += 1
    stopHeartbeat()
    const value = leaseRef.current
    leaseRef.current = null
    setLease(null)
    setPhase('released')
    await releaseRequest(value)
  }, [releaseRequest, stopHeartbeat])

  useEffect(() => {
    if (enabled && caseId && identity) void acquire(false)
    else {
      requestVersion.current += 1
      stopHeartbeat()
      leaseRef.current = null
      setLease(null)
      setPhase('idle')
    }
    return () => {
      requestVersion.current += 1
      stopHeartbeat()
      const value = leaseRef.current
      leaseRef.current = null
      void releaseRequest(value)
    }
  }, [acquire, caseId, enabled, identity, releaseRequest, stopHeartbeat])

  return { lease, phase, errorCode, acquire, release }
}
