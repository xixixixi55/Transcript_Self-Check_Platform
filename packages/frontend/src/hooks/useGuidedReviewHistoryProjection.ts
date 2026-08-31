// 第 10 层：FE_Hooks — 将当前报告草稿投影为历史预览的最终值摘要。
import type { FieldState, InspectionReport } from '@biji/shared/types'
import { hashAlgorithmLabel } from '@biji/shared/utils'

type FieldStates = Record<string, FieldState> | undefined

export type GuidedReviewHistoryTone = 'complete' | 'system' | 'warning' | 'recovered'

export interface GuidedReviewHistoryField {
  label: string
  value: string
  userProvided?: boolean
}

export interface GuidedReviewHistoryMaterial {
  id: string
  label: string
  fields: GuidedReviewHistoryField[]
  photoCount: number
  requiredPhotoCount: number
  userProvided?: boolean
}

export interface GuidedReviewHistoryItem {
  id: string
  tone: GuidedReviewHistoryTone
  title: string
  detail?: string
  fields?: GuidedReviewHistoryField[]
  materials?: GuidedReviewHistoryMaterial[]
}

function historyField(
  label: string,
  value: string | null | undefined,
  userProvided = false,
): GuidedReviewHistoryField | null {
  const normalized = value?.trim()
  return normalized ? { label, value: normalized, ...(userProvided ? { userProvided: true } : {}) } : null
}

function compactHistoryFields(
  fields: (GuidedReviewHistoryField | null)[],
): GuidedReviewHistoryField[] {
  return fields.filter((field): field is GuidedReviewHistoryField => field !== null)
}

function isUserProvided(fieldStates: FieldStates, ...paths: string[]): boolean {
  return paths.some(path => fieldStates?.[path]?.source === 'user')
}

function hasUserProvidedPrefix(fieldStates: FieldStates, prefix: string): boolean {
  return Object.entries(fieldStates || {}).some(([path, state]) =>
    path.startsWith(prefix) && state.source === 'user',
  )
}

function inspectorSummary(report: InspectionReport): string {
  const inspectors = report.introduction.inspector_snapshots
    || report.introduction.inspectors.map(item => ({
      name: item.name, unit: item.unit, position: item.position, police_number: item.badge_number,
    }))
  return inspectors.map(item => {
    const identity = [item.unit?.trim(), item.position?.trim(), item.police_number?.trim()]
      .filter(Boolean).join(' · ')
    return identity ? `${item.name.trim()}（${identity}）` : item.name.trim()
  }).filter(Boolean).join('、')
}

function hasCompleteInspectors(report: InspectionReport): boolean {
  const inspectors = report.introduction.inspector_snapshots
    || report.introduction.inspectors.map(item => ({
      name: item.name, unit: item.unit, police_number: item.badge_number,
    }))
  return inspectors.length > 0 && inspectors.every(item =>
    Boolean(item.name?.trim() && item.unit?.trim() && item.police_number?.trim()),
  )
}

function softwareSummary(report: InspectionReport): string {
  const primary = report.inspection.primary_software
  if (primary) return [primary.name?.trim(), primary.version?.trim()].filter(Boolean).join(' ')
    || primary.display_name?.trim()
  return [
    report.inspection.result.software_name?.trim(),
    report.inspection.result.software_version?.trim(),
  ].filter(Boolean).join(' ')
}

function materialPhotoCount(report: InspectionReport, materialIndex: number, materialId: string): number {
  const groups = report.attachments.photo_groups
  if (groups?.length) {
    const group = groups.find(item => item.material_id === materialId)
    if (group) return Math.min(2, group.ordered_image_ids.filter(Boolean).length)
  }
  return Math.min(2, Math.max(0, (report.attachments.photo_ids?.length || 0) - materialIndex * 2))
}

function materialHistory(report: InspectionReport, fieldStates: FieldStates): GuidedReviewHistoryMaterial[] {
  return report.introduction.evidence_list.map((material, index) => {
    const label = material.evidence_number?.trim()
      ? `检材 ${index + 1} · ${material.evidence_number.trim()}`
      : `检材 ${index + 1} · 编号待填写`
    const materialType = material.material_type === 'phone'
      ? '手机' : material.material_type === 'tablet' ? '平板' : null
    const brand = material.brand?.trim() || ''
    const model = material.model?.trim() || ''
    const deviceName = brand && model
      ? model.toLocaleLowerCase().includes(brand.toLocaleLowerCase()) ? model : `${brand} ${model}`
      : material.device_name?.trim() || model || material.device_type?.trim()
    const extractability = material.extractable === false
      ? material.unextractable_reason?.trim()
        ? `无法提取：${material.unextractable_reason.trim()}` : '无法提取'
      : material.extractable === true ? '可提取' : null
    const evidencePrefix = material.evidence_id ? `evidence.${material.evidence_id}.` : ''
    const evidencePath = (field: string) => evidencePrefix ? `${evidencePrefix}${field}` : ''
    const userProvided = material.material_type_source === 'user'
      || isUserProvided(fieldStates, 'introduction.evidence_list')
      || Boolean(evidencePrefix && hasUserProvidedPrefix(fieldStates, evidencePrefix))
    return {
      id: material.evidence_id || material.id || `material-${index}`,
      label,
      photoCount: materialPhotoCount(report, index, material.id),
      requiredPhotoCount: 2,
      ...(userProvided ? { userProvided: true } : {}),
      fields: compactHistoryFields([
        historyField('设备', deviceName, isUserProvided(fieldStates,
          evidencePath('device_name'), evidencePath('brand'), evidencePath('model'), evidencePath('device_type'))),
        historyField('类型', materialType, material.material_type_source === 'user'
          || isUserProvided(fieldStates, evidencePath('material_type'))),
        historyField('IMEI 1', material.imei1, isUserProvided(fieldStates, evidencePath('imei1'))),
        historyField('IMEI 2', material.imei2, isUserProvided(fieldStates, evidencePath('imei2'))),
        historyField('序列号', material.serial_number, isUserProvided(fieldStates, evidencePath('serial_number'))),
        historyField('提取情况', extractability, isUserProvided(fieldStates,
          evidencePath('extractable'), evidencePath('unextractable_reason'))),
      ]),
    }
  })
}

export function buildReportHistory(
  report: InspectionReport | null,
  fieldStates?: Record<string, FieldState>,
): GuidedReviewHistoryItem[] {
  if (!report) return []
  const history: GuidedReviewHistoryItem[] = []
  const introductionFields = compactHistoryFields([
    historyField('文号', report.document_number, isUserProvided(fieldStates, 'document_number')),
    historyField('委托单位前缀', report.introduction.entrust_unit_prefix,
      isUserProvided(fieldStates, 'introduction.entrust_unit_prefix')),
    historyField('委托单位', report.introduction.entrust_unit,
      isUserProvided(fieldStates, 'introduction.entrust_unit')),
    historyField('委托人员', report.introduction.entrust_persons.join('、'),
      isUserProvided(fieldStates, 'introduction.entrust_persons')),
    historyField('委托时间', report.introduction.entrust_time,
      isUserProvided(fieldStates, 'introduction.entrust_time')),
    historyField('案件简要情况', report.introduction.case_summary,
      isUserProvided(fieldStates, 'introduction.case_summary')),
    historyField('检查要求', report.introduction.inspection_requirement,
      isUserProvided(fieldStates, 'introduction.inspection_requirement')),
    historyField('检查起止时间', report.introduction.inspection_time_range,
      isUserProvided(fieldStates, 'introduction.inspection_time_range')),
  ])
  if (introductionFields.length) history.push({
    id: 'fact-report-recognition', tone: 'complete', title: '文书与委托信息已整理',
    fields: introductionFields,
  })

  const materials = materialHistory(report, fieldStates)
  if (materials.length) history.push({
    id: 'fact-evidence', tone: 'complete', title: `检材与图片 · ${materials.length} 项`, materials,
  })

  const inspectionFields = compactHistoryFields([
    historyField('检查人员', inspectorSummary(report),
      isUserProvided(fieldStates, 'introduction.inspectors')
        || hasUserProvidedPrefix(fieldStates, 'inspectors.')),
    historyField('检查地点', report.introduction.inspection_place,
      isUserProvided(fieldStates, 'introduction.inspection_place')),
    historyField('检查方法', report.inspection.method,
      isUserProvided(fieldStates, 'inspection.method')),
    historyField('硬件设备', report.inspection.hardware_device,
      isUserProvided(fieldStates, 'inspection.hardware_device')),
    historyField('主取证软件', softwareSummary(report), isUserProvided(fieldStates,
      'inspection.primary_software.name', 'inspection.primary_software.version',
      'inspection.result.software_name', 'inspection.result.software_version')),
    ...report.inspection.software_tools.map((tool, index) => historyField(
      `软件工具 ${index + 1}`,
      [tool.name?.trim(), tool.version?.trim()].filter(Boolean).join(' '),
      isUserProvided(fieldStates, 'inspection.software_tools'),
    )),
  ])
  const hasCompleteInspectionSettings = Boolean(
    report.introduction.inspection_place.trim()
    && report.inspection.method.trim()
    && report.inspection.hardware_device.trim()
    && hasCompleteInspectors(report),
  )
  if (inspectionFields.length) history.push({
    id: 'fact-defaults', tone: hasCompleteInspectionSettings ? 'complete' : 'system',
    title: hasCompleteInspectionSettings ? '检查信息已整理' : '检查信息正在整理',
    fields: inspectionFields,
  })

  const resultFields = compactHistoryFields([
    ...report.inspection.process_steps.map(step => historyField(
      `检查步骤 ${step.step_number}`, step.content,
      isUserProvided(fieldStates, 'inspection.process_steps'),
    )),
    historyField('检材编号', report.inspection.result.evidence_number,
      isUserProvided(fieldStates, 'inspection.result.evidence_number')),
    historyField('数据摘要', report.inspection.result.data_summary,
      isUserProvided(fieldStates, 'inspection.result.data_summary')),
    historyField('哈希算法', hashAlgorithmLabel(report.inspection.result.hash_algorithm),
      isUserProvided(fieldStates, 'inspection.result.hash_algorithm')),
    historyField('RAR 文件名', report.inspection.result.rar_filename,
      isUserProvided(fieldStates, 'inspection.result.rar_filename')),
    historyField('哈希值', report.inspection.result.md5_hash,
      isUserProvided(fieldStates, 'inspection.result.md5_hash')),
    historyField('文件大小', report.inspection.result.file_size,
      isUserProvided(fieldStates, 'inspection.result.file_size')),
    historyField('介质编号', report.attachments.disc_number,
      isUserProvided(fieldStates, 'attachments.disc_number')),
    historyField('刻录时间', report.attachments.burning_date,
      isUserProvided(fieldStates, 'attachments.burning_date')),
    historyField('提取方式', report.attachments.extraction_method,
      isUserProvided(fieldStates, 'attachments.extraction_method')),
  ])
  if (resultFields.length) history.push({
    id: 'fact-result', tone: 'complete', title: '检查结果已整理', fields: resultFields,
  })
  return history
}
