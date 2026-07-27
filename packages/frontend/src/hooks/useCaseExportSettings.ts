import { useEffect, useState } from 'react'
import type { InspectionReport } from '@biji/shared/types'
import { getDefaultExportFileName, validateExportFileName } from '@biji/shared/utils'

export function useCaseExportSettings(report: InspectionReport | null) {
  const [customFileName, setCustomFileNameState] = useState(false)
  const [exportFileName, setExportFileName] = useState('')
  const [exportFileNameError, setExportFileNameError] = useState('')

  useEffect(() => {
    if (report && !customFileName) setExportFileName(getDefaultExportFileName(report.document_number))
  }, [customFileName, report?.document_number])

  const setCustomFileName = (enabled: boolean) => {
    setCustomFileNameState(enabled)
    setExportFileNameError('')
    if (!enabled && report) setExportFileName(getDefaultExportFileName(report.document_number))
  }

  const setFileName = (value: string) => {
    setExportFileName(value)
    setExportFileNameError('')
  }

  const validate = () => {
    if (!customFileName) return null
    const error = validateExportFileName(exportFileName)
    setExportFileNameError(error || '')
    return error
  }

  return {
    customFileName,
    exportFileName,
    exportFileNameError,
    requestedFileName: customFileName
      ? exportFileName : getDefaultExportFileName(report?.document_number || ''),
    setCustomFileName,
    setFileName,
    setExportFileNameError,
    validate,
  }
}
