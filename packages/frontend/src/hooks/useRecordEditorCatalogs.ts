// Layer 10: FE_Hooks — shared managed-device and inspector catalogs for record editors.
import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { HardwareDevice, InspectorLibraryRecord } from '@biji/shared/types'

export function useRecordEditorCatalogs() {
  const [devices, setDevices] = useState<HardwareDevice[]>([])
  const [inspectors, setInspectors] = useState<InspectorLibraryRecord[]>([])
  const [deviceLoading, setDeviceLoading] = useState(true)
  const [inspectorLoading, setInspectorLoading] = useState(true)
  const [deviceError, setDeviceError] = useState<string | null>(null)
  const [inspectorError, setInspectorError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    axios.get<{ data?: HardwareDevice[] }>(API_ENDPOINTS.DEVICES)
      .then(response => {
        if (!active) return
        setDevices(response.data.data || [])
        setDeviceError(null)
      })
      .catch(() => {
        if (active) setDeviceError('获取电子设备失败，请稍后重试。')
      })
      .finally(() => {
        if (active) setDeviceLoading(false)
      })

    axios.get<{ data?: InspectorLibraryRecord[] }>(API_ENDPOINTS.INSPECTORS)
      .then(response => {
        if (!active) return
        setInspectors(response.data.data || [])
        setInspectorError(null)
      })
      .catch(() => {
        if (active) setInspectorError('获取检查人员失败，请稍后重试。')
      })
      .finally(() => {
        if (active) setInspectorLoading(false)
      })

    return () => { active = false }
  }, [])

  const deviceOptions = useMemo(
    () => devices.map(device => ({ label: device.name, value: device.name })),
    [devices],
  )

  return {
    devices,
    deviceOptions,
    inspectors,
    deviceLoading,
    inspectorLoading,
    deviceError,
    inspectorError,
  }
}
