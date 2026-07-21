// Layer 10: FE_Hooks — 笔录导出 Hook
import { useState, useCallback } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { ArchiveExecutionStatus, InspectionReport } from '@biji/shared/types'
import { getDefaultExportFileName, normalizeDataSummary, normalizeExportFileName } from '@biji/shared/utils'

interface UseRecordExportReturn {
  exportDocx: (report: InspectionReport, photoIds: string[], photoFiles?: File[], fileName?: string, archiveContextId?: string | null) => Promise<boolean>
  exporting: boolean
  archiveStatus: ArchiveExecutionStatus
}

const EXPORT_BLOCKER_MESSAGES: Record<string, string> = {
  ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID: '每个检材必须对应两张图片，请检查各检材的正反面照片。',
  ATTACHMENT2_IMAGE_MAPPING_INVALID: '附件2图片与检材的归属或顺序无效，请在审核页重新确认检材分组。',
  WINRAR_UNAVAILABLE: 'WinRAR 不可用，请安装并确保可以调用。',
  ARCHIVE_INPUT_EMPTY: '归档输入为空，无法生成归档。',
  ARCHIVE_INPUT_CHANGED: '归档输入已变化，请重新解析报告后重试。',
  ARCHIVE_TOO_LARGE: '归档输入超过 135GB 上限。',
  ARCHIVE_PLAN_INVALID: '归档计划无效，请检查案件名称和输入文件。',
  ARCHIVE_EXECUTION_FAILED: '归档执行失败，请检查后重试。',
  ARCHIVE_EXECUTION_TIMEOUT: '归档执行超时，请确认系统资源充足后重试。',
  ARCHIVE_INTEGRITY_TIMEOUT: '归档完整性校验超时，请确认系统资源充足后重试。',
  ARCHIVE_PARTS_INVALID: '归档分卷或完整性校验失败，请重新生成。',
  ARCHIVE_MANIFEST_MISSING: '缺少已验证的归档清单，请重新生成归档。',
  ARCHIVE_MANIFEST_INVALID: '归档清单校验失败，请重新生成归档。',
  ARCHIVE_MANIFEST_CONTEXT_MISMATCH: '归档清单不属于当前案件，请重新生成归档。',
  ARCHIVE_MANIFEST_PART_MISSING: '归档分卷已缺失，请重新生成归档。',
  ARCHIVE_MANIFEST_PART_CHANGED: '归档分卷已变化，请重新生成归档。',
  ARCHIVE_REPLAN_EXHAUSTED: '归档重规划次数已用尽，请检查输入文件。',
  ARCHIVE_CONTEXT_INVALID: '归档上下文已过期，请重新解析报告。',
  ARCHIVE_EXECUTION_IN_PROGRESS: '归档正在执行，请稍后重试。',
  PRIMARY_SOFTWARE_UNCONFIRMED: '主取证软件名称和版本必须先确认。',
  FIRST_DISC_NUMBER_MISSING: '首个光盘编号不能为空。',
  FIRST_DISC_NUMBER_INVALID: '首个光盘编号格式或日期无效。',
  DISC_SEQUENCE_INVALID: '光盘编号必须先通过校验。',
  DOCUMENT_EXPORT_FAILED: '文档生成失败，请检查模板后重试。',
  ATTACHMENT2_IMAGE_COUNT_ODD: '附件图片数量必须为偶数，请补充或删除一张图片后重新导出。',
  ODD_PHOTO_COUNT: '附件图片数量必须为偶数，请补充或删除一张图片后重新导出。',
  ATTACHMENT2_IMAGE_INVALID: '附件图片无法读取、解码或格式不受支持，请更换后重试。',
  ATTACHMENT_PLAN_INVALID: '附件页面计划无效，请重新生成归档。',
  TEMPLATE_PROFILE_MISMATCH: '当前 Word 模板资产不匹配，请联系管理员。',
  DOCX_RENDER_FAILED: 'Word 页面渲染失败，请检查模板后重试。',
}

const ARCHIVE_INPUT_MESSAGES: Record<string, string> = {
  ARCHIVE_INPUT_ROOT_NOT_ALLOWED: '所选案件目录未获授权，请重新解析案件目录。',
  ARCHIVE_INPUT_PATH_INVALID: '所选案件目录无效，请重新选择并解析。',
  ARCHIVE_INPUT_LINK_NOT_ALLOWED: '输入目录包含不支持的链接或特殊路径，请重新解析。',
  ARCHIVE_INPUT_OUTPUT_OVERLAP: '输入目录与输出区域冲突，请重新选择。',
  ARCHIVE_CONTEXT_NOT_FOUND: '归档上下文不存在，请重新解析报告。',
  ARCHIVE_CONTEXT_EXPIRED: '归档上下文已过期，请重新解析报告。',
  ARCHIVE_CONTEXT_BUSY: '归档上下文正在执行，请稍后重试。',
  ARCHIVE_AUTHORIZATION_INVALID: '目录授权无效，请重新选择案件目录。',
  ARCHIVE_AUTHORIZATION_EXPIRED: '目录授权已过期，请重新选择案件目录。',
}

Object.assign(EXPORT_BLOCKER_MESSAGES, ARCHIVE_INPUT_MESSAGES)

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
  if (typeof detail?.code === 'string') return EXPORT_BLOCKER_MESSAGES[detail.code] || '导出失败，请重试。'
  return error.message || '导出失败'
}

function buildMaterialPhotoGroups(report: InspectionReport, photoCount: number) {
  const evidenceList = report.introduction?.evidence_list || []
  const groupCount = Math.floor(photoCount / 2)
  return evidenceList.slice(0, groupCount).map((item, index) => ({
    material_id: item.id,
    material_number: item.evidence_number,
    display_text: `检材${item.evidence_number}照片`,
    ordered_image_ids: [`photo-${index * 2 + 1}`, `photo-${index * 2 + 2}`] as [string, string],
    source_order: index + 1,
  }))
}

export function useRecordExport(): UseRecordExportReturn {
  const [exporting, setExporting] = useState(false)
  const [archiveStatus, setArchiveStatus] = useState<ArchiveExecutionStatus>('idle')

  const exportDocx = useCallback(async (
    report: InspectionReport,
    photoIds: string[],
    photoFiles?: File[],
    fileName?: string,
    archiveContextId?: string | null,
  ) => {
    setExporting(true)
    setArchiveStatus('planning')
    try {
      const normalizedReport = JSON.parse(JSON.stringify(report)) as InspectionReport
      normalizedReport.inspection.result.data_summary = normalizeDataSummary(
        normalizedReport.inspection.result.data_summary,
      )
      const photoCount = photoIds.length
      const runtimePhotoIds = photoIds.map((_, index) => `photo-${index + 1}`)
      const reportJson = JSON.stringify({
        ...normalizedReport,
        attachments: {
          ...normalizedReport.attachments,
          photo_ids: runtimePhotoIds,
          photo_groups: buildMaterialPhotoGroups(normalizedReport, photoCount),
        },
      })
      const archiveForm = new FormData()
      archiveForm.append('report_json', reportJson)
      archiveForm.append('archive_context_id', archiveContextId || '')
      setArchiveStatus('compressing')
      const archiveResponse = await axios.post<{ data: { manifest_id: string } }>(
        API_ENDPOINTS.EXECUTE_ARCHIVE, archiveForm,
      )
      const manifestId = archiveResponse.data.data.manifest_id
      if (!manifestId) throw new Error('ARCHIVE_MANIFEST_MISSING')
      setArchiveStatus('validating')

      const formData = new FormData()
      formData.append('report_json', reportJson)
      formData.append('archive_context_id', archiveContextId || '')
      formData.append('manifest_id', manifestId)
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
      setArchiveStatus('completed')
      return true
    } catch (e: any) {
      setArchiveStatus('failed')
      alert('导出失败: ' + await resolveExportErrorMessage(e))
      return false
    } finally {
      setExporting(false)
    }
  }, [])

  return { exportDocx, exporting, archiveStatus }
}
