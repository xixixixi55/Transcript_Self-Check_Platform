import type { InspectionReport } from '@biji/shared/types'
import { isValidDateFieldValue, isValidMinuteTimeRangeValue, parseDiscSequence } from '@biji/shared/utils'

export type ReviewPendingSeverity = 'warning' | 'error'

export interface ReviewPendingItem {
  id: string
  sectionId: string
  targetId: string
  sectionLabel: string
  fieldLabel: string
  reason: string
  severity: ReviewPendingSeverity
}

export const REVIEW_SECTION_IDS = {
  archive: 'review-section-archive',
  document: 'review-section-document',
  introduction: 'review-section-introduction',
  inspection: 'review-section-inspection',
  attachments: 'review-section-attachments',
} as const

export const REVIEW_TARGET_IDS = {
  documentNumber: 'review-target-document-number',
  entrustUnit: 'review-target-entrust-unit',
  entrustPersons: 'review-target-entrust-persons',
  entrustTime: 'review-target-entrust-time',
  caseSummary: 'review-target-case-summary',
  inspectionRequirement: 'review-target-inspection-requirement',
  inspectionTimeRange: 'review-target-inspection-time-range',
  inspectionPlace: 'review-target-inspection-place',
  inspectionMethod: 'review-target-inspection-method',
  hardwareDevice: 'review-target-hardware-device',
  primarySoftwareName: 'review-target-primary-software-name',
  primarySoftwareVersion: 'review-target-primary-software-version',
  primarySoftwareStatus: 'review-target-primary-software-status',
  discNumber: 'review-target-first-disc-number',
  burningDate: 'review-target-burning-date',
  exportFileName: 'review-target-document-number',
  evidence: (index: number) => `review-target-evidence-${index}`,
  inspector: (index: number) => `review-target-inspector-${index}`,
  softwareTool: (index: number) => `review-target-software-tool-${index}`,
  processStep: (index: number) => `review-target-process-step-${index}`,
  result: (key: string) => `review-target-result-${key}`,
} as const

export const REVIEW_REVEAL_TARGET_EVENT = 'review:reveal-target'

function isBlank(value: unknown): boolean {
  return typeof value !== 'string' || value.trim() === ''
}

function effectiveEvidenceDeviceType(item: InspectionReport['introduction']['evidence_list'][number]): string {
  const explicit = item.device_type?.trim() || item.device_name?.trim() || item.model?.trim()
  if (explicit) return explicit
  if (item.material_type === 'phone' && item.material_type_status === 'confirmed_by_user') return '手机'
  if (item.material_type === 'tablet' && item.material_type_status === 'confirmed_by_user') return '平板'
  return ''
}

function addBlankItem(
  items: ReviewPendingItem[],
  sectionId: string,
  targetId: string,
  sectionLabel: string,
  fieldLabel: string,
  value: unknown,
) {
  if (isBlank(value)) {
    items.push({
      id: `${sectionId}-${fieldLabel}`,
      sectionId,
      targetId,
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
  targetId: string,
  sectionLabel: string,
  fieldLabel: string,
  reason: string,
) {
  items.push({
    id: `${sectionId}-${fieldLabel}-invalid`,
    sectionId,
    targetId,
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

  addBlankItem(items, REVIEW_SECTION_IDS.document, REVIEW_TARGET_IDS.documentNumber, '文书信息', '文号', report.document_number)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.entrustUnit, '一、绪论', '委托单位', introduction?.entrust_unit)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.entrustPersons, '一、绪论', '委托人员', introduction?.entrust_persons?.join('、'))
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.entrustTime, '一、绪论', '委托时间', introduction?.entrust_time)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.caseSummary, '一、绪论', '案件简要情况', introduction?.case_summary)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.inspectionRequirement, '一、绪论', '检查要求', introduction?.inspection_requirement)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.inspectionTimeRange, '一、绪论', '检查起止时间', introduction?.inspection_time_range)
  addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.inspectionPlace, '一、绪论', '检查地点', introduction?.inspection_place)

  introduction?.evidence_list?.forEach((item, index) => {
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.evidence(index), '一、绪论', `检材${index + 1}设备类型`, effectiveEvidenceDeviceType(item))
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.evidence(index), '一、绪论', `检材${index + 1}编号`, item.evidence_number)
    if (item.material_type !== 'phone' && item.material_type !== 'tablet'
      || item.material_type_status !== 'confirmed_by_report' && item.material_type_status !== 'confirmed_by_user'
      || item.material_type_source !== 'report' && item.material_type_source !== 'user') {
      addInvalidItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.evidence(index), '一、绪论', `检材${index + 1}类型`, '必须确认检材为手机或平板后才能导出。')
    }
  })
  const inspectorSnapshots = introduction?.inspector_snapshots
    || (introduction?.inspectors || []).map(item => ({
      name: item.name,
      unit: item.unit,
      police_number: item.badge_number,
    }))
  inspectorSnapshots.forEach((item, index) => {
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.inspector(index), '一、绪论', `检查人员${index + 1}姓名`, item.name)
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.inspector(index), '一、绪论', `检查人员${index + 1}单位`, item.unit)
    addBlankItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.inspector(index), '一、绪论', `检查人员${index + 1}警号`, item.police_number)
  })

  addBlankItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.inspectionMethod, '二、检查', '检查方法', inspection?.method)
  addBlankItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.hardwareDevice, '二、检查', '硬件设备', inspection?.hardware_device)
  inspection?.software_tools?.forEach((item, index) => {
    addBlankItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.softwareTool(index), '二、检查', `软件工具${index + 1}名称`, item.name)
    addBlankItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.softwareTool(index), '二、检查', `软件工具${index + 1}版本`, item.version)
  })
  const primarySoftware = inspection?.primary_software
  addBlankItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.primarySoftwareName, '二、检查', '主取证软件名称', primarySoftware?.name)
  addBlankItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.primarySoftwareVersion, '二、检查', '主取证软件版本', primarySoftware?.version)
  if (primarySoftware?.confirmation_status !== 'confirmed_by_report'
    && primarySoftware?.confirmation_status !== 'confirmed_by_user') {
    addInvalidItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.primarySoftwareStatus, '二、检查', '主取证软件确认状态', '主取证软件名称和版本必须确认后才能导出。')
  }
  inspection?.process_steps?.forEach((item, index) => {
    addBlankItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.processStep(index), '二、检查', `检查步骤${index + 1}`, item.content)
  })
  ;[
    ['检材编号', result?.evidence_number],
    ['数据摘要', result?.data_summary],
    ['RAR 文件名', result?.rar_filename],
    ['MD5 哈希', result?.md5_hash],
    ['文件大小', result?.file_size],
  ].forEach(([label, value], index) => {
    const key = ['evidence_number', 'data_summary', 'rar_filename', 'md5_hash', 'file_size'][index]
    addBlankItem(items, REVIEW_SECTION_IDS.inspection, REVIEW_TARGET_IDS.result(key), '二、检查', label, value)
  })

  addBlankItem(items, REVIEW_SECTION_IDS.archive, REVIEW_TARGET_IDS.discNumber, '附件', '光盘编号', attachments?.disc_number)
  if (attachments?.disc_number && !parseDiscSequence(attachments.disc_number).valid) {
    addInvalidItem(items, REVIEW_SECTION_IDS.archive, REVIEW_TARGET_IDS.discNumber, '附件', '光盘编号', '首个光盘编号必须符合 GPyyyyMMdd-序号 格式且日期真实有效。')
  }
  if (exportFileNameError) {
    items.push({
      id: 'review-export-file-name',
      sectionId: REVIEW_SECTION_IDS.document,
      targetId: REVIEW_TARGET_IDS.exportFileName,
      sectionLabel: '文书信息',
      fieldLabel: '导出文件名',
      reason: exportFileNameError,
      severity: 'error',
    })
  }

  if (introduction?.entrust_time && !isValidDateFieldValue(introduction.entrust_time)) {
    addInvalidItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.entrustTime, '一、绪论', '委托时间', '日期格式无法通过现有校验。')
  }
  if (introduction?.inspection_time_range && !isValidMinuteTimeRangeValue(introduction.inspection_time_range)) {
    addInvalidItem(items, REVIEW_SECTION_IDS.introduction, REVIEW_TARGET_IDS.inspectionTimeRange, '一、绪论', '检查起止时间', '时间范围无法通过现有校验。')
  }
  if (attachments?.burning_date && !isValidDateFieldValue(attachments.burning_date)) {
    addInvalidItem(items, REVIEW_SECTION_IDS.attachments, REVIEW_TARGET_IDS.burningDate, '附件', '刻录时间', '日期格式无法通过现有校验。')
  }

  return items
}
