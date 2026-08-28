// 第 10 层：FE_Hooks — 预览阶段的归档生命周期。
import {
  useCallback, useEffect, useRef, useState,
  type Dispatch, type SetStateAction,
} from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type {
  ArchiveExecutionResponse,
  ArchiveLifecycleStatus,
  ArchiveManifest,
  InspectionReport,
} from '@biji/shared/types'

interface ArchivePreparation {
  status: ArchiveLifecycleStatus
  loading: boolean
  manifest: ArchiveManifest | null
  attachmentPreview: InspectionReport['attachments']['extract_list'] | null
  error: string | null
  prepare: (report: InspectionReport, contextId: string, attemptId?: string | null) => Promise<void>
  reset: () => void
}

const ARCHIVE_STATUSES = new Set<ArchiveLifecycleStatus>([
  'not_prepared', 'preparing', 'ready', 'failed', 'idle', 'waiting',
  'planning', 'blocked', 'compressing', 'validating', 'hashing', 'completed',
])

function lifecycleStatus(value: unknown): ArchiveLifecycleStatus | null {
  return typeof value === 'string' && ARCHIVE_STATUSES.has(value as ArchiveLifecycleStatus)
    ? value as ArchiveLifecycleStatus
    : null
}

export function resolveArchivePreparationError(error: any): string {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'object' && detail !== null) {
    if (typeof detail.message === 'string') return detail.message
    if (typeof detail.code === 'string') return `归档准备失败（${detail.code}），请重试。`
    const blocker = detail.blockers?.[0]
    if (typeof blocker?.message === 'string') return blocker.message
  }
  if (error?.code === 'ERR_CANCELED' || error?.name === 'AbortError') return '归档准备已取消。'
  return '归档准备失败，请检查审核内容后重试。'
}

export function useArchivePreparation(): ArchivePreparation {
  const [status, setStatus] = useState<ArchiveLifecycleStatus>('not_prepared')
  const [loading, setLoading] = useState(false)
  const [manifest, setManifest] = useState<ArchiveManifest | null>(null)
  const [attachmentPreview, setAttachmentPreview] = useState<InspectionReport['attachments']['extract_list'] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const requestRef = useRef<AbortController | null>(null)
  const attemptRef = useRef(0)
  const pollRef = useRef<number | null>(null)
  const mountedRef = useRef(true)
  const activeKey = useRef('')

  useEffect(() => () => {
    mountedRef.current = false
    requestRef.current?.abort()
    if (pollRef.current !== null) window.clearInterval(pollRef.current)
  }, [])

  const reset = useCallback(() => {
    requestRef.current?.abort()
    requestRef.current = null
    attemptRef.current += 1
    if (pollRef.current !== null) window.clearInterval(pollRef.current)
    pollRef.current = null
    activeKey.current = ''
    setLoading(false)
    setStatus('not_prepared')
    setManifest(null)
    setAttachmentPreview(null)
    setError(null)
  }, [])

  const prepare = useCallback(async (report: InspectionReport, contextId: string, attemptId?: string | null) => {
    if (requestRef.current) return
    const discNumber = String(report.attachments?.disc_number || '').trim()
    const key = [contextId, report.introduction?.case_summary || '', discNumber].join('|')
    if (!discNumber) {
      activeKey.current = ''
      setStatus('failed')
      setManifest(null)
      setError('请先填写有效的首个光盘编号，再开始归档准备。')
      return
    }
    if (activeKey.current === key) return
    activeKey.current = key
    const controller = new AbortController()
    const attempt = attemptRef.current + 1
    attemptRef.current = attempt
    requestRef.current = controller
    setLoading(true)
    setStatus('preparing')
    setManifest(null)
    setError(null)
    const form = new FormData()
    form.append('archive_context_id', contextId)
    if (attemptId) form.append('archive_attempt_id', attemptId)
    form.append('report_json', JSON.stringify(report))
    const isCurrent = () => mountedRef.current
      && attemptRef.current === attempt && requestRef.current === controller
    const poll = window.setInterval(async () => {
      try {
        const response = await axios.get(API_ENDPOINTS.ARCHIVE_STATUS(contextId), { signal: controller.signal })
        const next = lifecycleStatus(response.data?.data?.status)
        if (isCurrent() && next) setStatus(next === 'completed' ? 'ready' : next)
      } catch {
        // 正在执行的请求负责记录最终的稳定错误。
      }
    }, 500)
    pollRef.current = poll
    try {
      const response = await axios.post<{ data: ArchiveExecutionResponse }>(
        API_ENDPOINTS.EXECUTE_ARCHIVE, form, { signal: controller.signal },
      )
      if (!response.data.data.manifest) throw new Error('ARCHIVE_MANIFEST_MISSING')
      if (!isCurrent()) return
      setManifest(response.data.data.manifest)
      setAttachmentPreview(response.data.data.attachment_preview || null)
      setStatus('ready')
    } catch (failure: any) {
      if (!isCurrent()) return
      activeKey.current = ''
      if (controller.signal.aborted) {
        setStatus('not_prepared')
        setError(null)
      } else {
        setStatus('failed')
      }
      const blocker = failure.response?.data?.detail?.blockers?.[0]
      setError(blocker?.message || '归档失败；可以继续审核，但正式导出已被阻止。')
      if (!controller.signal.aborted) setError(resolveArchivePreparationError(failure))
    } finally {
      window.clearInterval(poll)
      if (pollRef.current === poll) pollRef.current = null
      if (isCurrent()) {
        requestRef.current = null
        setLoading(false)
      }
    }
  }, [])

  return { status, loading, manifest, attachmentPreview, error, prepare, reset }
}

export function usePreviewArchive(
  _report: InspectionReport | null,
  setReport: Dispatch<SetStateAction<InspectionReport | null>>,
  contextId: string | null,
): ArchivePreparation {
  const archive = useArchivePreparation()
  useEffect(() => {
    archive.reset()
  }, [archive.reset, contextId])
  useEffect(() => {
    if (!archive.manifest) return
    const parts = archive.manifest.parts
    setReport(current => current ? {
      ...current,
      inspection: {
        ...current.inspection,
        result: {
          ...current.inspection.result,
          rar_filename: parts.map(part => part.filename).join('、'),
          md5_hash: parts.map(part => part.md5).join('、'),
          file_size: parts.map(part => String(part.size_bytes)).join('、'),
        },
      },
      attachments: archive.attachmentPreview ? {
        ...current.attachments,
        extract_list: archive.attachmentPreview,
      } : current.attachments,
    } : current)
  }, [archive.manifest, archive.attachmentPreview, setReport])
  return archive
}
