import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import type { ClientIdentity, EditLease } from '@biji/shared/types'
import { useEditLease } from './useEditLease'

vi.mock('axios', () => ({ default: { post: vi.fn() } }))
const postMock = vi.mocked(axios.post)
const identity: ClientIdentity = { client_instance_id: 'client-synthetic', session_id: 'session-synthetic', deployment_instance_id: 'local', observed_at: '2026-01-01T00:00:00.000Z', identity_kind: 'local_session' }
const lease: EditLease = { schema_version: 1, lease_id: 'lease-synthetic', case_id: 'case-synthetic', session_id: identity.session_id, client_instance_id: identity.client_instance_id, lease_token: 'token-synthetic', last_heartbeat_at: '2026-01-01T00:00:00Z', expires_at: '2026-01-01T00:02:00Z', status: 'active', takeover_of_lease_id: null, revision: 0 }

describe('useEditLease', () => {
  beforeEach(() => { vi.clearAllMocks(); postMock.mockResolvedValue({ data: { data: lease } }) })

  it('acquires and releases the lease', async () => {
    const view = renderHook(() => useEditLease({ caseId: 'case-synthetic', identity, enabled: true }))
    await waitFor(() => expect(view.result.current.phase).toBe('active'))
    await act(async () => { await view.result.current.release() })
    expect(postMock).toHaveBeenCalledWith(expect.stringContaining('/release'), expect.anything())
    expect(postMock).toHaveBeenCalledWith(expect.stringContaining('/workbench/cases/case-synthetic/lease'), expect.anything())
  })

  it('enters read-only mode when another active session owns the case', async () => {
    postMock.mockRejectedValue({ response: { data: { detail: { code: 'LEASE_CONFLICT' } } } })
    const view = renderHook(() => useEditLease({ caseId: 'case-synthetic', identity, enabled: true }))
    await waitFor(() => expect(view.result.current.phase).toBe('read_only'))
    expect(view.result.current.errorCode).toBe('LEASE_CONFLICT')
  })
})
