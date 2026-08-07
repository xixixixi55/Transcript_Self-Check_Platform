import type { InspectionReport, InspectorSnapshot } from '../types'
import { formatDiscDate, parseDiscSequence } from './discSequenceUtils'

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
  return next
}
