// Layer 10: FE_Hooks — deferred disc mapping and unified export actions.
import { useCallback, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS, EXPORT_DIRECTORY_PICKER_TIMEOUT_MS, WORKBENCH_REQUEST_TIMEOUT_MS } from '@biji/shared/constants'
import type { DiscMappingResult, ExportDirectoryResult, UnifiedExportResult } from '@biji/shared/types'

interface ArchiveCompletion {
  mapping: (caseId: string, expectedRevision: number, firstDiscNumber: string) => Promise<DiscMappingResult>
  exportBundle: (caseId: string, expectedRevision: number, exportPath: string, directoryToken: string, wordFilename: string) => Promise<UnifiedExportResult>
  chooseDirectory: () => Promise<ExportDirectoryResult>
  busy: boolean
  error: string | null
}

function detailMessage(error: unknown): string {
  const detail = (error as any)?.response?.data?.detail
  if (typeof detail?.message === 'string') return detail.message
  if (typeof detail?.code === 'string') return `操作失败（${detail.code}）。`
  return '操作失败，请稍后重试。'
}

export function useArchiveCompletion(): ArchiveCompletion {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mapping = useCallback(async (caseId: string, expectedRevision: number, firstDiscNumber: string) => {
    setBusy(true)
    setError(null)
    try {
      const response = await axios.post<{ data: DiscMappingResult }>(
        API_ENDPOINTS.WORKBENCH_ARCHIVE_DISC_MAPPING(caseId),
        { expected_revision: expectedRevision, first_disc_number: firstDiscNumber },
        { timeout: WORKBENCH_REQUEST_TIMEOUT_MS },
      )
      return response.data.data
    } catch (failure) {
      setError(detailMessage(failure))
      throw failure
    } finally {
      setBusy(false)
    }
  }, [])

  const exportBundle = useCallback(async (
    caseId: string, expectedRevision: number, exportPath: string,
    directoryToken: string, wordFilename: string,
  ) => {
    setBusy(true)
    setError(null)
    try {
      const response = await axios.post<{ data: UnifiedExportResult }>(
        API_ENDPOINTS.WORKBENCH_UNIFIED_EXPORT(caseId),
        {
          expected_revision: expectedRevision, export_path: exportPath,
          directory_token: directoryToken, word_filename: wordFilename,
        },
        { timeout: WORKBENCH_REQUEST_TIMEOUT_MS },
      )
      return response.data.data
    } catch (failure) {
      setError(detailMessage(failure))
      throw failure
    } finally {
      setBusy(false)
    }
  }, [])

  const chooseDirectory = useCallback(async (): Promise<ExportDirectoryResult> => {
    setBusy(true)
    setError(null)
    try {
      const response = await axios.post<{ data: ExportDirectoryResult }>(
        API_ENDPOINTS.WORKBENCH_SELECT_EXPORT_DIRECTORY,
        undefined,
        { timeout: EXPORT_DIRECTORY_PICKER_TIMEOUT_MS },
      )
      return response.data.data
    } catch (failure) {
      setError(detailMessage(failure))
      throw failure
    } finally {
      setBusy(false)
    }
  }, [])

  return { mapping, exportBundle, chooseDirectory, busy, error }
}
