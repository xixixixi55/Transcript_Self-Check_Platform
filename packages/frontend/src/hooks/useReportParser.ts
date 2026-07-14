// Layer 10: FE_Hooks — 报告解析 Hook
import { useState, useCallback } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { ParseReportResponse } from '@biji/shared/types'

interface UseReportParserReturn {
  parseReport: (dirPath: string, compress?: boolean) => Promise<ParseReportResponse | null>
  parseArchive: (file: File) => Promise<ParseReportResponse | null>
  loading: boolean
  error: string | null
  result: ParseReportResponse | null
}

export function useReportParser(): UseReportParserReturn {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ParseReportResponse | null>(null)

  const parseReport = useCallback(async (dirPath: string, compress: boolean = true) => {
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('report_dir', dirPath)
      formData.append('compress', String(compress))
      const { data } = await axios.post<{ success: boolean; data: ParseReportResponse }>(
        API_ENDPOINTS.PARSE_REPORT, formData,
      )
      setResult(data.data)
      return data.data
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || '解析失败')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const parseArchive = useCallback(async (file: File) => {
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('archive_file', file)
      const { data } = await axios.post<{ success: boolean; data: ParseReportResponse }>(
        API_ENDPOINTS.PARSE_REPORT, formData,
      )
      setResult(data.data)
      return data.data
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || '压缩包解析失败')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  return { parseReport, parseArchive, loading, error, result }
}
