// Layer 10: FE_Hooks — 笔录导出 Hook
import { useState, useCallback } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { InspectionReport } from '@biji/shared/types'

interface UseRecordExportReturn {
  exportDocx: (report: InspectionReport, photoIds: string[], photoFiles?: File[]) => Promise<void>
  exporting: boolean
}

export function useRecordExport(): UseRecordExportReturn {
  const [exporting, setExporting] = useState(false)

  const exportDocx = useCallback(async (report: InspectionReport, photoIds: string[], photoFiles?: File[]) => {
    setExporting(true)
    try {
      const formData = new FormData()
      formData.append('report_json', JSON.stringify({ ...report, attachments: { ...report.attachments, photo_ids: photoIds } }))
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
      a.download = `${report.document_number || '检查笔录'}.docx`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (e: any) {
      alert('导出失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setExporting(false)
    }
  }, [])

  return { exportDocx, exporting }
}
