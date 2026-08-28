// 第 10 层：FE_Hooks - 已停用的兼容辅助函数；工作台默认值由后端持久化。
/** @deprecated 案件工作台使用 /workbench/defaults；此辅助函数仅为旧测试适配器保留。 */
import { useCallback, useState } from 'react'
import type { InspectionReport, InspectorSnapshot } from '@biji/shared/types'
import { generateDiscNumbers, parseDiscSequence } from '@biji/shared/utils'

const STORAGE_KEY = 'biji.reportDefaults.v1'

export interface ReportUserDefaults {
  document_number: string
  inspection_place: string
  inspection_method: string
  hardware_device: string
  inspector_snapshots: InspectorSnapshot[]
  disc_number_prefix: string
}

const EMPTY_DEFAULTS: ReportUserDefaults = {
  document_number: '', inspection_place: '', inspection_method: '', hardware_device: '',
  inspector_snapshots: [], disc_number_prefix: '',
}

const clean = (value: unknown, limit = 500) => String(value || '')
  .replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, limit)

export function readReportDefaults(storage: Pick<Storage, 'getItem'> = window.localStorage): ReportUserDefaults {
  try {
    const raw = JSON.parse(storage.getItem(STORAGE_KEY) || '{}')
    return {
      document_number: clean(raw.document_number, 100),
      inspection_place: clean(raw.inspection_place, 200),
      inspection_method: clean(raw.inspection_method),
      hardware_device: clean(raw.hardware_device, 200),
      inspector_snapshots: Array.isArray(raw.inspector_snapshots) ? raw.inspector_snapshots.map((item: any) => ({
        inspector_id: clean(item.inspector_id, 100) || undefined,
        name: clean(item.name, 100), unit: clean(item.unit, 200), position: clean(item.position, 100),
        police_number: clean(item.police_number, 100), selected_order: Number(item.selected_order) || 0,
      })).filter((item: InspectorSnapshot) => item.name) : [],
      disc_number_prefix: clean(raw.disc_number_prefix, 20),
    }
  } catch { return { ...EMPTY_DEFAULTS } }
}

function writeReportDefaults(value: ReportUserDefaults): void {
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value)) } catch { /* unavailable storage */ }
}

export function applyReportDefaults(report: InspectionReport, defaults: ReportUserDefaults): InspectionReport {
  const next = JSON.parse(JSON.stringify(report)) as InspectionReport
  if (defaults.document_number) next.document_number = defaults.document_number
  if (defaults.inspection_place) next.introduction.inspection_place = defaults.inspection_place
  if (defaults.inspection_method) next.inspection.method = defaults.inspection_method
  if (defaults.hardware_device) next.inspection.hardware_device = defaults.hardware_device
  if (defaults.inspector_snapshots.length) {
    next.introduction.inspector_snapshots = defaults.inspector_snapshots
    next.introduction.inspectors = defaults.inspector_snapshots.map(item => ({
      name: item.name, unit: item.unit, position: item.position, badge_number: item.police_number,
    }))
  }
  const parsed = parseDiscSequence(next.attachments.disc_number || '')
  if (defaults.disc_number_prefix && parsed.valid && parsed.sequence) {
    next.attachments.disc_number = generateDiscNumbers({ ...parsed.sequence, prefix: defaults.disc_number_prefix }, 1)[0]
  }
  return next
}

export function useReportDefaults() {
  const [defaults, setDefaults] = useState(readReportDefaults)
  const persist = useCallback((next: ReportUserDefaults) => { writeReportDefaults(next); setDefaults(next) }, [])
  const saveCurrentReport = useCallback((report: InspectionReport) => persist({
    document_number: clean(report.document_number, 100),
    inspection_place: clean(report.introduction.inspection_place, 200),
    inspection_method: clean(report.inspection.method),
    hardware_device: clean(report.inspection.hardware_device, 200),
    inspector_snapshots: JSON.parse(JSON.stringify(report.introduction.inspector_snapshots
      || report.introduction.inspectors.map(item => ({
        name: item.name, unit: item.unit, position: item.position, police_number: item.badge_number,
      })))),
    disc_number_prefix: defaults.disc_number_prefix,
  }), [defaults.disc_number_prefix, persist])
  const saveDiscPrefix = useCallback((prefix: string) => persist({
    ...defaults, disc_number_prefix: clean(prefix, 20),
  }), [defaults, persist])
  const clearDefaults = useCallback(() => {
    try { window.localStorage.removeItem(STORAGE_KEY) } catch { /* unavailable storage */ }
    setDefaults({ ...EMPTY_DEFAULTS })
  }, [])
  const applyDefaults = useCallback((report: InspectionReport) => applyReportDefaults(report, readReportDefaults()), [])
  const hasDefaults = Boolean(defaults.document_number || defaults.inspection_place || defaults.inspection_method
    || defaults.hardware_device || defaults.inspector_snapshots.length || defaults.disc_number_prefix)
  return { defaults, hasDefaults, saveCurrentReport, saveDiscPrefix, clearDefaults, applyDefaults }
}
