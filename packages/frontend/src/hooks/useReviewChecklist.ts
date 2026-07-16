import type { InspectionReport } from '@biji/shared/types'
import { isValidDateFieldValue, isValidMinuteTimeRangeValue } from '@biji/shared/utils'

export type ReviewPendingSeverity = 'warning' | 'error'

export interface ReviewPendingItem {
  id: string
  sectionId: string
  sectionLabel: string
  fieldLabel: string
  reason: string
  severity: ReviewPendingSeverity
}

export const REVIEW_SECTION_IDS = {
  document: 'review-section-document',
  introduction: 'review-section-introduction',
  inspection: 'review-section-inspection',
  attachments: 'review-section-attachments',
} as const

function isBlank(value: unknown): boolean {
  return typeof value !== 'string' || value.trim() === ''
}

function addBlankItem(
  items: ReviewPendingItem[],
  sectionId: string,
  sectionLabel: string,
  fieldLabel: string,
  value: unknown,
) {
  if (isBlank(value)) {
    items.push({
      id: `${sectionId}-${fieldLabel}`,
      sectionId,
      sectionLabel,
      fieldLabel,
      reason: '当前字段为空，仅作为基础待核对提示，不等同于业务必填校验。',
      severity: 'warning',
    })
  }
}

function addInvalidItem(
  items: ReviewPendingItem[],
  sectionId: string,
  sectionLabel: string,
  fieldLabel: string,
  reason: string,
) {
  items.push({
    id: `${sectionId}-${fieldLabel}-invalid`,
    sectionId,
    sectionLabel,
    fieldLabel,
    reason,
    severity: 'error',
  })
}

export function getReviewPendingItems(
  report: InspectionReport,
  exportFileNameError?: string,
): ReviewPendingItem[] {
  const items: ReviewPendingItem[] = []
  const introduction = report.introduction
  const inspection = report.inspection
  const result = inspection?.result
  const attachments = report.attachments

  addBlankItem(items, REVIEW_SECTION_IDS.document, '文书信息', '文号', report.document_number)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '委托单位', introduction?.entrust_unit)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '委托人员', introduction?.entrust_persons?.join('、'))
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '委托时间', introduction?.entrust_time)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '案件简要情况', introduction?.case_summary)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '检查要求', introduction?.inspection_requirement)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '检查起止时间', introduction?.inspection_time_range)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '检查地点', introduction?.inspection_place)

  introduction?.evidence_list?.forEach((item, index) => {
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', `检材${index + 1}设备类型`, item.device_type)
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', `检材${index + 1}编号`, item.evidence_number)
  })
  introduction?.inspectors?.forEach((item, index) => {
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', `检查人员${index + 1}姓名`, item.name)
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', `检查人员${index + 1}单位`, item.unit)
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', `检查人员${index + 1}警号`, item.badge_number)
  })

  addBlankItem(items, REVIEW_SECTION_IDS.inspection, '二、检查', '检查方法', inspection?.method)
  addBlankItem(items, REVIEW_SECTION_IDS.inspection, '二、检查', '硬件设备', inspection?.hardware_device)
  inspection?.software_tools?.forEach((item, index) => {
    addBlankItem(items, REVIEW_SECTION_IDS.inspection, '二、检查', `软件工具${index + 1}名称`, item.name)
    addBlankItem(items, REVIEW_SECTION_IDS.inspection, '二、检查', `软件工具${index + 1}版本`, item.version)
  })
  inspection?.process_steps?.forEach((item, index) => {
    addBlankItem(items, REVIEW_SECTION_IDS.inspection, '二、检查', `检查步骤${index + 1}`, item.content)
  })
  ;[
    ['检材编号', result?.evidence_number],
    ['软件名称', result?.software_name],
    ['软件版本', result?.software_version],
    ['数据摘要', result?.data_summary],
    ['RAR 文件名', result?.rar_filename],
    ['MD5 哈希', result?.md5_hash],
    ['文件大小', result?.file_size],
  ].forEach(([label, value]) => addBlankItem(items, REVIEW_SECTION_IDS.inspection, '二、检查', label, value))

  addBlankItem(items, REVIEW_SECTION_IDS.attachments, '附件', '光盘编号', attachments?.disc_number)
  if (exportFileNameError) {
    items.push({
      id: 'review-export-file-name',
      sectionId: REVIEW_SECTION_IDS.document,
      sectionLabel: '文书信息',
      fieldLabel: '导出文件名',
      reason: exportFileNameError,
      severity: 'error',
    })
  }

  if (introduction?.entrust_time && !isValidDateFieldValue(introduction.entrust_time)) {
    addInvalidItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '委托时间', '日期格式无法通过现有校验。')
  }
  if (introduction?.inspection_time_range && !isValidMinuteTimeRangeValue(introduction.inspection_time_range)) {
    addInvalidItem(items, REVIEW_SECTION_IDS.introduction, '一、绪论', '检查起止时间', '时间范围无法通过现有校验。')
  }
  if (attachments?.burning_date && !isValidDateFieldValue(attachments.burning_date)) {
    addInvalidItem(items, REVIEW_SECTION_IDS.attachments, '附件', '刻录时间', '日期格式无法通过现有校验。')
  }

  return items
}
