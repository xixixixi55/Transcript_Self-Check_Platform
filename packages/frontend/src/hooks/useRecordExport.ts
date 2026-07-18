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

const EXPORT_BLOCKER_MESSAGES: Record<string, string> = {
  PRIMARY_SOFTWARE_UNCONFIRMED: '主取证软件名称和版本必须先确认。',
  FIRST_DISC_NUMBER_MISSING: '首个光盘编号不能为空。',
  FIRST_DISC_NUMBER_INVALID: '首个光盘编号格式或日期无效。',
  DISC_SEQUENCE_INVALID: '光盘编号必须先通过校验。',
}

function formatExportBlockers(blockers: Array<{ code?: string }>): string {
  return blockers.map(item => EXPORT_BLOCKER_MESSAGES[item.code || ''] || '导出门控未通过。').join('；')
}

export function resolveExportFileName(documentNumber: string, requestedFileName?: string): string {
  return requestedFileName
    ? normalizeExportFileName(requestedFileName)
    : getDefaultExportFileName(documentNumber)
}

async function resolveExportErrorMessage(error: any): Promise<string> {
  const responseData = error.response?.data
  if (responseData instanceof Blob) {
    try {
      const parsed = JSON.parse(await responseData.text())
      const blockers = parsed.detail?.blockers
      if (Array.isArray(blockers) && blockers.length > 0) {
        return formatExportBlockers(blockers)
      }
      if (typeof parsed.detail === 'string') return parsed.detail
    } catch {
      // Fall through to the generic Axios error below.
    }
  }
  const detail = responseData?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail?.blockers)) return formatExportBlockers(detail.blockers)
  return error.message || '导出失败'
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
      alert('导出失败: ' + await resolveExportErrorMessage(e))
      return false
    } finally {
      setExporting(false)
    }
  }, [])

  return { exportDocx, exporting }
}
