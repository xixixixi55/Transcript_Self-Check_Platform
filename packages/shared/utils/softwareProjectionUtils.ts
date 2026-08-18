import type { EvidenceItem, InspectionReport, InspectorSnapshot, ProcessStep } from '../types'
import { formatDiscDate, parseDiscSequence } from './discSequenceUtils'
import { buildMaterialPhotoGroups } from './materialPhotoGroups'
import { projectInspectionEnvironmentStep } from './inspectionEnvironmentUtils'

function text(value: unknown): string {
  return value == null ? '' : String(value).trim()
}

function softwareActionName(value: unknown): string {
  const name = text(value) || '待确认主取证软件'
  return name.endsWith('软件') ? name : `${name}软件`
}

function evidenceDeviceName(item: EvidenceItem): string {
  const brand = text(item.brand)
  const model = text(item.model)
  if (brand && model) {
    return model.toLocaleLowerCase().includes(brand.toLocaleLowerCase())
      ? model : `${brand} ${model}`
  }
  return text(item.device_name) || model || text(item.device_type) || '未知设备'
}

function evidenceIdentifiers(item: EvidenceItem): string {
  if (!isEvidenceExtractable(item)) return '无法提取'
  const imeiValues = [text(item.imei1), text(item.imei2)].filter(Boolean)
  const serialNumber = text(item.serial_number)
  const identifiers = item.material_type === 'tablet'
    ? (serialNumber ? [`序列号：${serialNumber}`] : [])
    : item.material_type === 'phone'
      ? imeiValues.map((value, index) => `IMEI${index + 1}：${value}`)
      : [
          ...imeiValues.map((value, index) => `IMEI${index + 1}：${value}`),
          ...(serialNumber ? [`序列号：${serialNumber}`] : []),
        ]
  return identifiers.join('；') || '设备标识待确认'
}

function isEvidenceExtractable(item: EvidenceItem): boolean {
  if (typeof item.extractable === 'boolean') return item.extractable
  return Boolean(text(item.imei1) || text(item.imei2) || text(item.serial_number))
}

function projectEvidenceProcessSteps(report: InspectionReport): ProcessStep[] {
  const evidenceList = report.introduction.evidence_list || []
  const evidenceNumbers = evidenceList.map(item => text(item.evidence_number)).filter(Boolean)
  const evidenceLabel = evidenceNumbers.join('、') || 'xx'
  const descriptions = evidenceList.map(item =>
    `${evidenceDeviceName(item)}（${evidenceIdentifiers(item)}）编号为${text(item.evidence_number) || 'xx'}`,
  )
  const primary = report.inspection.primary_software
  const softwareName = text(primary?.name) || text(report.inspection.result.software_name)
  const softwareVersion = text(primary?.version) || text(report.inspection.result.software_version)
  const softwareDisplay = softwareActionName(softwareName)
  const projectedContent = new Map<number, string>([
    [1, descriptions.length ? `将${descriptions.join('；')}。` : '将检材信息待确认。'],
    [2, `对检材${evidenceLabel}进行拍照。`],
    [4, `启动${softwareDisplay}（版本号为${softwareVersion || '待确认'}）使用${softwareDisplay}对检材${evidenceLabel}进行检查。`],
  ])
  return (report.inspection.process_steps || []).map(step => ({
    ...step,
    content: projectedContent.get(step.step_number) ?? step.content,
  }))
}

function applyEvidenceListProjection(report: InspectionReport): InspectionReport {
  const evidenceNumbers = report.introduction.evidence_list
    .map(item => text(item.evidence_number))
    .filter(Boolean)
  report.inspection.result.evidence_number = evidenceNumbers.join('、')
  report.inspection.process_steps = projectEvidenceProcessSteps(report)
  report.attachments.photo_groups = buildMaterialPhotoGroups(report, report.attachments.photo_ids || [])
  return report
}

export function applyPrimarySoftwareEdit(
  report: InspectionReport,
  field: 'name' | 'version',
  value: string,
): InspectionReport {
  const next = JSON.parse(JSON.stringify(report)) as InspectionReport
  next.inspection.primary_software = next.inspection.primary_software || {
    name: next.inspection.result.software_name || '',
    version: next.inspection.result.software_version || '',
    display_name: '',
    confirmation_status: 'unconfirmed',
    provenance: [],
    candidates: [],
  }
  next.inspection.primary_software[field] = value
  const primary = next.inspection.primary_software
  primary.display_name = [primary.name, primary.version].filter(Boolean).join(' ')
  primary.confirmation_status = primary.name.trim() && primary.version.trim()
    ? 'confirmed_by_user' : 'unconfirmed'
  next.inspection.result.software_name = primary.name
  next.inspection.result.software_version = primary.version
  const runtimeTools = (next.inspection.software_tools || []).filter(tool =>
    ['WinRAR压缩管理软件', 'Python hashlib', 'HashMyFiles'].includes(tool.name),
  )
  next.inspection.software_tools = primary.name && primary.version
    ? [{ name: primary.name, version: primary.version }, ...runtimeTools]
    : runtimeTools
  next.inspection.process_steps = projectEvidenceProcessSteps(next).map((step, index) =>
    step.step_number === 4 ? step : next.inspection.process_steps[index] || step,
  )
  return next
}

export function applyReportEdit(report: InspectionReport, path: string, value: any): InspectionReport {
  const primaryField = path === 'inspection.primary_software.name' ? 'name'
    : path === 'inspection.primary_software.version' ? 'version' : null
  const next = primaryField ? applyPrimarySoftwareEdit(report, primaryField, value)
    : JSON.parse(JSON.stringify(report)) as InspectionReport
  if (!primaryField) {
    const keys = path.split('.')
    let target: any = next
    for (let index = 0; index < keys.length - 1; index += 1) target = target[keys[index]]
    target[keys[keys.length - 1]] = value
    if (path === 'attachments.disc_number') {
      const parsed = parseDiscSequence(value)
      next.attachments.burning_date = parsed.valid && parsed.sequence ? formatDiscDate(parsed.sequence.date) : ''
      next.attachments.disc_sequence = parsed.valid ? parsed.sequence : undefined
    }
  }
  if (path === 'introduction.inspector_snapshots') {
    next.introduction.inspectors = (value as InspectorSnapshot[]).map(snapshot => ({
      name: snapshot.name, unit: snapshot.unit, badge_number: snapshot.police_number,
    }))
  }
  if (path === 'inspection.hardware_device' && next.inspection.environment_snapshot) {
    next.inspection.process_steps = projectInspectionEnvironmentStep(
      next.inspection.process_steps || [],
      next.inspection.hardware_device,
      next.inspection.environment_snapshot,
    )
  }
  return path === 'introduction.evidence_list' ? applyEvidenceListProjection(next) : next
}
