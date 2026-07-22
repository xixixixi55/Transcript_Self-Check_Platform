// Layer 10: FE_Hooks — preview-stage archive lifecycle.
import {
  useCallback, useEffect, useRef, useState,
  type Dispatch, type SetStateAction,
} from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type {
  ArchiveExecutionResponse,
  ArchiveExecutionStatus,
  ArchiveManifest,
  InspectionReport,
} from '@biji/shared/types'

interface ArchivePreparation {
  status: ArchiveExecutionStatus
  manifest: ArchiveManifest | null
  attachmentPreview: InspectionReport['attachments']['extract_list'] | null
  error: string | null
  prepare: (report: InspectionReport, contextId: string) => Promise<void>
  reset: () => void
}

export function useArchivePreparation(): ArchivePreparation {
  const [status, setStatus] = useState<ArchiveExecutionStatus>('idle')
  const [manifest, setManifest] = useState<ArchiveManifest | null>(null)
  const [attachmentPreview, setAttachmentPreview] = useState<InspectionReport['attachments']['extract_list'] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const activeKey = useRef('')

  const reset = useCallback(() => {
    activeKey.current = ''
    setStatus('idle')
    setManifest(null)
    setAttachmentPreview(null)
    setError(null)
  }, [])

  const prepare = useCallback(async (report: InspectionReport, contextId: string) => {
    const discNumber = String(report.attachments?.disc_number || '').trim()
    const key = [contextId, report.introduction?.case_summary || '', discNumber].join('|')
    if (!discNumber) {
      activeKey.current = ''
      setStatus('waiting')
      setManifest(null)
      setError('填写首个光盘编号后将自动开始归档。')
      return
    }
    if (activeKey.current === key) return
    activeKey.current = key
    setStatus('planning')
    setManifest(null)
    setError(null)
    const form = new FormData()
    form.append('archive_context_id', contextId)
    form.append('report_json', JSON.stringify(report))
    const poll = window.setInterval(async () => {
      try {
        const response = await axios.get(API_ENDPOINTS.ARCHIVE_STATUS(contextId))
        const next = response.data?.data?.status as ArchiveExecutionStatus | undefined
        if (next) setStatus(next)
      } catch {
        // The executing request owns the final stable error.
      }
    }, 500)
    try {
      const response = await axios.post<{ data: ArchiveExecutionResponse }>(
        API_ENDPOINTS.EXECUTE_ARCHIVE, form,
      )
      if (!response.data.data.manifest) throw new Error('ARCHIVE_MANIFEST_MISSING')
      setManifest(response.data.data.manifest)
      setAttachmentPreview(response.data.data.attachment_preview || null)
      setStatus('completed')
    } catch (failure: any) {
      activeKey.current = ''
      setStatus('failed')
      const blocker = failure.response?.data?.detail?.blockers?.[0]
      setError(blocker?.message || '归档失败；可以继续审核，但正式导出已被阻止。')
    } finally {
      window.clearInterval(poll)
    }
  }, [])

  return { status, manifest, attachmentPreview, error, prepare, reset }
}

export function usePreviewArchive(
  report: InspectionReport | null,
  setReport: Dispatch<SetStateAction<InspectionReport | null>>,
  contextId: string | null,
): ArchivePreparation {
  const archive = useArchivePreparation()
  useEffect(() => {
    if (!report || !contextId) return
    void archive.prepare(report, contextId)
  }, [
    archive.prepare,
    contextId,
    report?.introduction?.case_summary,
    report?.attachments?.disc_number,
  ])
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
