// Layer 10: FE_Hooks — deployment-scoped shared-default settings state.
import { useCallback, useEffect, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { HashAlgorithm, SharedDefaults } from '@biji/shared/types'
import { createClientIdentity } from './useEditLease'

export interface SharedInspectorDefault {
  name: string
  unit: string
  badgeNumber: string
}

export interface SharedDefaultsFormValues {
  entrustUnitPrefix: string
  documentNumber: string
  inspectionPlace: string
  inspectionMethod: string
  hardwareDevice: string
  inspectors: SharedInspectorDefault[]
  discNumberPrefix: string
  hashAlgorithm: HashAlgorithm
}

export type SharedDefaultsSettingsStatus = 'idle' | 'loading' | 'saving' | 'saved' | 'conflict' | 'failed'
export type SharedDefaultsFailedOperation = 'load' | 'save' | null

function parseInspector(value: string): SharedInspectorDefault {
  const [name = '', unit = '', badgeNumber = ''] = value.split('|')
  return { name, unit, badgeNumber }
}

export function sharedDefaultsToForm(defaults: SharedDefaults): SharedDefaultsFormValues {
  return {
    entrustUnitPrefix: defaults.entrust_unit_prefix,
    documentNumber: defaults.document_number,
    inspectionPlace: defaults.inspection_place,
    inspectionMethod: defaults.inspection_method,
    hardwareDevice: defaults.hardware_device,
    inspectors: defaults.inspector_order.map(parseInspector),
    discNumberPrefix: defaults.disc_number_prefix,
    hashAlgorithm: defaults.hash_algorithm || 'md5',
  }
}

export function sharedDefaultsPatch(values: SharedDefaultsFormValues): Record<string, unknown> {
  return {
    entrust_unit_prefix: values.entrustUnitPrefix,
    document_number: values.documentNumber,
    inspection_place: values.inspectionPlace,
    inspection_method: values.inspectionMethod,
    hardware_device: values.hardwareDevice,
    inspector_order: values.inspectors.map(item => (
      `${item.name.trim()}|${item.unit.trim()}|${item.badgeNumber.trim()}`
    )),
    disc_number_prefix: values.discNumberPrefix,
    hash_algorithm: values.hashAlgorithm,
  }
}

function errorCode(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: { code?: unknown } } } })
    ?.response?.data?.detail
  return typeof detail?.code === 'string' ? detail.code : 'SHARED_DEFAULTS_REQUEST_FAILED'
}

export function useSharedDefaultsSettings() {
  const [defaults, setDefaults] = useState<SharedDefaults | null>(null)
  const [status, setStatus] = useState<SharedDefaultsSettingsStatus>('idle')
  const [requestErrorCode, setRequestErrorCode] = useState<string | null>(null)
  const [failedOperation, setFailedOperation] = useState<SharedDefaultsFailedOperation>(null)

  const load = useCallback(async () => {
    setStatus('loading')
    setRequestErrorCode(null)
    setFailedOperation(null)
    try {
      const response = await axios.get<{ data: SharedDefaults }>(API_ENDPOINTS.WORKBENCH_DEFAULTS)
      setDefaults(response.data.data)
      setStatus('idle')
      return response.data.data
    } catch (error) {
      setRequestErrorCode(errorCode(error))
      setFailedOperation('load')
      setStatus('failed')
      return null
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const save = useCallback(async (values: SharedDefaultsFormValues) => {
    if (!defaults || status === 'saving' || status === 'loading') return null
    setStatus('saving')
    setRequestErrorCode(null)
    setFailedOperation(null)
    try {
      const response = await axios.put<{ data: SharedDefaults }>(API_ENDPOINTS.WORKBENCH_DEFAULTS, {
        values: sharedDefaultsPatch(values),
        expected_revision: defaults.revision,
        identity: createClientIdentity(defaults.deployment_instance_id),
      })
      setDefaults(response.data.data)
      setStatus('saved')
      return response.data.data
    } catch (error) {
      const code = errorCode(error)
      setRequestErrorCode(code)
      setFailedOperation(code === 'REVISION_CONFLICT' ? null : 'save')
      setStatus(code === 'REVISION_CONFLICT' ? 'conflict' : 'failed')
      return null
    }
  }, [defaults, status])

  return { defaults, status, requestErrorCode, failedOperation, load, save }
}
