// Layer 10: FE_Hooks - report parsing and safe authorization diagnostics.
import { useState, useCallback, useRef } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { ClearReportParsingCacheResponse, ParseReportResponse } from '@biji/shared/types'
import { normalizeDataSummary } from '@biji/shared/utils'

interface UseReportParserReturn {
  parseReport: (dirPath: string, compress?: boolean) => Promise<ParseReportResponse | null>
  parseArchive: (file: File) => Promise<ParseReportResponse | null>
  loading: boolean
  error: string | null
  errorCode: string | null
  result: ParseReportResponse | null
  clearReportParsingCache: () => Promise<ClearReportParsingCacheResponse | null>
  clearingCache: boolean
  cacheClearMessage: string | null
  cacheClearError: string | null
}

const PARSE_ERROR_MESSAGES: Record<string, string> = {
  ARCHIVE_INPUT_ROOT_NOT_ALLOWED: '所选案件目录未获授权，请选择允许目录或重新解析。',
  ARCHIVE_INPUT_PATH_INVALID: '所选案件目录无效，请重新选择。',
  ARCHIVE_INPUT_LINK_NOT_ALLOWED: '所选目录包含不支持的链接或特殊路径，请重新选择。',
  ARCHIVE_INPUT_OUTPUT_OVERLAP: '所选目录与系统输出区域冲突，请重新选择。',
  ARCHIVE_AUTHORIZATION_INVALID: '目录授权无效，请重新选择案件目录。',
  ARCHIVE_AUTHORIZATION_EXPIRED: '目录授权已过期，请重新选择案件目录。',
}

const CACHE_CLEAR_ERROR_MESSAGES: Record<string, string> = {
  REPORT_PARSING_CACHE_CLEAR_FAILED: '解析缓存清理失败，请重试。',
}

export interface ParseErrorInfo {
  code: string | null
  message: string
}

export function resolveParseError(error: any): ParseErrorInfo {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'object' && detail !== null) {
    const code = typeof detail.code === 'string' ? detail.code : null
    return {
      code,
      message: PARSE_ERROR_MESSAGES[code || ''] || detail.message || '解析失败，请检查输入后重试。',
    }
  }
  return {
    code: null,
    message: typeof detail === 'string' ? detail : error?.message || '解析失败，请检查输入后重试。',
  }
}

export function resolveCacheClearError(error: any): string {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'object' && detail !== null) {
    const code = typeof detail.code === 'string' ? detail.code : ''
    return CACHE_CLEAR_ERROR_MESSAGES[code] || '解析缓存清理失败，请重试。'
  }
  return '解析缓存清理失败，请重试。'
}

/** Normalize parsed data before it enters the editor, without exposing server paths. */
export function normalizeParsedReport(response: ParseReportResponse): ParseReportResponse {
  const normalized = JSON.parse(JSON.stringify(response)) as ParseReportResponse
  normalized.report.inspection.result.data_summary = normalizeDataSummary(
    normalized.report.inspection.result.data_summary,
  )
  return normalized
}

export function useReportParser(): UseReportParserReturn {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorCode, setErrorCode] = useState<string | null>(null)
  const [result, setResult] = useState<ParseReportResponse | null>(null)
  const [clearingCache, setClearingCache] = useState(false)
  const [cacheClearMessage, setCacheClearMessage] = useState<string | null>(null)
  const [cacheClearError, setCacheClearError] = useState<string | null>(null)
  const clearBusy = useRef(false)

  const parseReport = useCallback(async (dirPath: string, compress: boolean = true) => {
    setLoading(true)
    setError(null)
    setErrorCode(null)
    try {
      const formData = new FormData()
      formData.append('report_dir', dirPath)
      formData.append('compress', String(compress))
      const { data } = await axios.post<{ success: boolean; data: ParseReportResponse }>(
        API_ENDPOINTS.PARSE_REPORT, formData,
      )
      const normalized = normalizeParsedReport(data.data)
      setResult(normalized)
      return normalized
    } catch (error: any) {
      const failure = resolveParseError(error)
      setErrorCode(failure.code)
      setError(failure.message)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const parseArchive = useCallback(async (file: File) => {
    setLoading(true)
    setError(null)
    setErrorCode(null)
    try {
      const formData = new FormData()
      formData.append('archive_file', file)
      const { data } = await axios.post<{ success: boolean; data: ParseReportResponse }>(
        API_ENDPOINTS.PARSE_REPORT, formData,
      )
      const normalized = normalizeParsedReport(data.data)
      setResult(normalized)
      return normalized
    } catch (error: any) {
      const failure = resolveParseError(error)
      setErrorCode(failure.code)
      setError(failure.message)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const clearReportParsingCache = useCallback(async () => {
    if (clearBusy.current) return null
    clearBusy.current = true
    setClearingCache(true)
    setCacheClearMessage(null)
    setCacheClearError(null)
    try {
      const { data } = await axios.delete<{
        success: boolean
        data: ClearReportParsingCacheResponse
      }>(API_ENDPOINTS.CLEAR_REPORT_PARSING_CACHE)
      const cleared = data.data?.cleared_count || 0
      const clearResult = { cleared_count: cleared }
      setCacheClearMessage(cleared > 0
        ? `已清理 ${cleared} 条解析缓存。清空后下次需要重新解析报告。`
        : '当前没有可清理的缓存。清空后下次需要重新解析报告。')
      return clearResult
    } catch (failure: any) {
      setCacheClearError(resolveCacheClearError(failure))
      return null
    } finally {
      clearBusy.current = false
      setClearingCache(false)
    }
  }, [])

  return {
    parseReport, parseArchive, loading, error, errorCode, result,
    clearReportParsingCache, clearingCache, cacheClearMessage, cacheClearError,
  }
}
