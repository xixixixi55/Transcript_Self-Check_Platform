import { useCallback, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS, EXPORT_DIRECTORY_PICKER_TIMEOUT_MS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import type { ArchiveStorageSettings } from '@biji/shared/types'

interface SelectionResult {
  cancelled: boolean
  settings: ArchiveStorageSettings
}

function failureMessage(error: unknown): string {
  const detail = (error as any)?.response?.data?.detail
  if (typeof detail?.message === 'string') return detail.message
  return '归档目录设置未完成，请稍后重试。'
}

export function useArchiveStorageSettings() {
  const [settings, setSettings] = useState<ArchiveStorageSettings | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async <T,>(action: () => Promise<T>): Promise<T> => {
    setLoading(true)
    setError(null)
    try {
      return await action()
    } catch (failure) {
      setError(failureMessage(failure))
      throw failure
    } finally {
      setLoading(false)
    }
  }, [])

  const load = useCallback(() => run(async () => {
    const response = await axios.get<{ data: ArchiveStorageSettings }>(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_STORAGE_SETTINGS,
      { timeout: WORKBENCH_REQUEST_TIMEOUT_MS },
    )
    setSettings(response.data.data)
    return response.data.data
  }), [run])

  const selectDirectory = useCallback(() => run(async () => {
    const response = await axios.post<{ data: SelectionResult }>(
      API_ENDPOINTS.WORKBENCH_SELECT_ARCHIVE_STORAGE_DIRECTORY,
      undefined,
      { timeout: EXPORT_DIRECTORY_PICKER_TIMEOUT_MS },
    )
    setSettings(response.data.data.settings)
    return response.data.data
  }), [run])

  const reset = useCallback(() => run(async () => {
    const response = await axios.delete<{ data: ArchiveStorageSettings }>(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_STORAGE_SETTINGS,
      { timeout: WORKBENCH_REQUEST_TIMEOUT_MS },
    )
    setSettings(response.data.data)
    return response.data.data
  }), [run])

  return { settings, loading, error, load, selectDirectory, reset }
}
