// Layer 10: FE_Hooks — 笔录导出 Hook
import { useState, useCallback } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { InspectionReport } from '@biji/shared/types'
import { getDefaultExportFileName, normalizeDataSummary, normalizeExportFileName } from '@biji/shared/utils'

interface UseRecordExportReturn {
  exportDocx: (report: InspectionReport, photoIds: string[], photoFiles?: File[], fileName?: string) => Promise<boolean>
  exporting: boolean
}

export function resolveExportFileName(documentNumber: string, requestedFileName?: string): string {
  return requestedFileName
    ? normalizeExportFileName(requestedFileName)
    : getDefaultExportFileName(documentNumber)
}

export function useRecordExport(): UseRecordExportReturn {
  const [exporting, setExporting] = useState(false)

  const exportDocx = useCallback(async (
    report: InspectionReport,
    photoIds: string[],
    photoFiles?: File[],
    fileName?: string,
  ) => {
    setExporting(true)
    try {
      const formData = new FormData()
      const normalizedReport = JSON.parse(JSON.stringify(report)) as InspectionReport
      normalizedReport.inspection.result.data_summary = normalizeDataSummary(
        normalizedReport.inspection.result.data_summary,
      )
      formData.append('report_json', JSON.stringify({
        ...normalizedReport,
        attachments: { ...normalizedReport.attachments, photo_ids: photoIds },
      }))
      // 附加图片文件
      if (photoFiles) {
        photoFiles.forEach(f => formData.append('photos', f))
      }
      const response = await axios.post(API_ENDPOINTS.EXPORT_RECORD, formData, {
        responseType: 'blob',
      })
      // 触发浏览器下载
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = resolveExportFileName(report.document_number, fileName)
      a.click()
      window.URL.revokeObjectURL(url)
      return true
    } catch (e: any) {
      alert('导出失败: ' + (e.response?.data?.detail || e.message))
      return false
    } finally {
      setExporting(false)
    }
  }, [])

  return { exportDocx, exporting }
}
