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
  document_number: 'SYNTHETIC-DOC',
  document_number_template: { prefix: 'SYN-TEST〔2026〕', suffix: '号' },
  inspection_place: 'SYNTHETIC-PLACE', inspection_method: 'SYNTHETIC-METHOD',
  hardware_device: 'SYNTHETIC-DEVICE',
  inspector_order: ['SYNTHETIC-NAME|SYNTHETIC-UNIT|SYNTHETIC-POSITION|SYNTHETIC-001'],
  disc_number_prefix: 'GP', extraction_method: 'SYNTHETIC-EXTRACTION-METHOD',
  inspection_requirement: 'SYNTHETIC-INSPECTION-REQUIREMENT',
  data_summary: 'SYNTHETIC-DATA-SUMMARY',
  hash_algorithm: 'sha256', migration_decision: 'ignored', updated_at: '2026-08-23T00:00:00Z',
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
    values.documentNumberPrefix = 'SYN-TEST〔2027〕'
    values.documentNumberSuffix = '号'
    expect(sharedDefaultsPatch(values, defaults.document_number, true)).toEqual(expect.objectContaining({
      document_number: '',
      document_number_template: { prefix: 'SYN-TEST〔2027〕', suffix: '号' },
      inspector_order: ['SYNTHETIC-NAME|SYNTHETIC-UNIT|SYNTHETIC-POSITION|SYNTHETIC-001'],
      inspection_requirement: 'SYNTHETIC-INSPECTION-REQUIREMENT',
      data_summary: 'SYNTHETIC-DATA-SUMMARY',
      hash_algorithm: 'sha256',
    }))
    expect(sharedDefaultsPatch(values, defaults.document_number, true)).not.toHaveProperty('disc_number_prefix')
    expect(sharedDefaultsPatch(values, defaults.document_number, true)).not.toHaveProperty('extraction_method')
    expect(sharedDefaultsPatch(values, defaults.document_number, true)).not.toHaveProperty('entrust_unit_prefix')

    await act(async () => { await result.current.save(values) })

    expect(putMock).toHaveBeenCalledWith(API_ENDPOINTS.WORKBENCH_DEFAULTS, {
      values: expect.objectContaining({
        document_number: '',
        document_number_template: { prefix: 'SYN-TEST〔2027〕', suffix: '号' },
      }),
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

  it('preserves a legacy complete document-number default until a format is configured', () => {
    const legacyDefaults = {
      ...defaults,
      document_number: 'SYNTHETIC-LEGACY-DOC',
      document_number_template: undefined,
    }
    const values = sharedDefaultsToForm(legacyDefaults)

    expect(sharedDefaultsPatch(values, legacyDefaults.document_number, false)).toEqual(
      expect.objectContaining({
        document_number: 'SYNTHETIC-LEGACY-DOC',
        document_number_template: { prefix: '', suffix: '' },
      }),
    )
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
