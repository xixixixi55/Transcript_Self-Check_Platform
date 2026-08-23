import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { SharedDefaults } from '@biji/shared/types'
import {
  sharedDefaultsPatch, sharedDefaultsToForm, useSharedDefaultsSettings,
} from './useSharedDefaultsSettings'

vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const putMock = vi.mocked(axios.put)
const defaults: SharedDefaults = {
  schema_version: 1, deployment_instance_id: 'SYNTHETIC-DEPLOYMENT', revision: 4,
  entrust_unit_prefix: 'SYNTHETIC-PREFIX', document_number: 'SYNTHETIC-DOC',
  inspection_place: 'SYNTHETIC-PLACE', inspection_method: 'SYNTHETIC-METHOD',
  hardware_device: 'SYNTHETIC-DEVICE',
  inspector_order: ['SYNTHETIC-NAME|SYNTHETIC-UNIT|SYNTHETIC-POSITION|SYNTHETIC-001'],
  disc_number_prefix: 'GP', hash_algorithm: 'sha256', migration_decision: 'ignored', updated_at: '2026-08-23T00:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
  getMock.mockResolvedValue({ data: { data: defaults } })
  putMock.mockResolvedValue({ data: { data: { ...defaults, revision: 5, document_number: '' } } })
})

describe('useSharedDefaultsSettings', () => {
  it('loads, serializes ordered inspectors, and explicitly saves cleared values', async () => {
    const { result } = renderHook(() => useSharedDefaultsSettings())
    await waitFor(() => expect(result.current.defaults?.revision).toBe(4))

    const values = sharedDefaultsToForm(defaults)
    values.documentNumber = '   '
    expect(sharedDefaultsPatch(values)).toEqual(expect.objectContaining({
      document_number: '   ',
      inspector_order: ['SYNTHETIC-NAME|SYNTHETIC-UNIT|SYNTHETIC-POSITION|SYNTHETIC-001'],
      hash_algorithm: 'sha256',
    }))

    await act(async () => { await result.current.save(values) })

    expect(putMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_DEFAULTS, {
      values: expect.objectContaining({ document_number: '   ' }),
      expected_revision: 4,
      identity: expect.objectContaining({
        deployment_instance_id: 'SYNTHETIC-DEPLOYMENT', identity_kind: 'local_session',
      }),
    })
    expect(result.current.status).toBe('saved')
    expect(result.current.defaults?.revision).toBe(5)
  })

  it('reports a revision conflict without replacing the loaded values', async () => {
    putMock.mockRejectedValue({ response: { data: { detail: { code: 'REVISION_CONFLICT' } } } })
    const { result } = renderHook(() => useSharedDefaultsSettings())
    await waitFor(() => expect(result.current.defaults?.revision).toBe(4))

    await act(async () => { await result.current.save(sharedDefaultsToForm(defaults)) })

    expect(result.current.status).toBe('conflict')
    expect(result.current.defaults?.revision).toBe(4)
  })

  it('distinguishes a reload failure and keeps the last loaded values', async () => {
    const { result } = renderHook(() => useSharedDefaultsSettings())
    await waitFor(() => expect(result.current.defaults?.revision).toBe(4))
    getMock.mockRejectedValueOnce({ response: { data: { detail: { code: 'SYNTHETIC_LOAD_FAILED' } } } })

    await act(async () => { await result.current.load() })

    expect(result.current.status).toBe('failed')
    expect(result.current.failedOperation).toBe('load')
    expect(result.current.requestErrorCode).toBe('SYNTHETIC_LOAD_FAILED')
    expect(result.current.defaults?.revision).toBe(4)
  })
})
