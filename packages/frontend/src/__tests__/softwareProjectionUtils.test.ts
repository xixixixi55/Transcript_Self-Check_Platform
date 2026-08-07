import { describe, expect, it } from 'vitest'
import type { InspectionReport } from '@biji/shared/types'
import { applyPrimarySoftwareEdit } from '@biji/shared/utils'

const report: InspectionReport = {
  title: '合成笔录', document_number: 'DOC-001',
  introduction: {
    entrust_unit: '', entrust_persons: [], entrust_time: '', case_summary: '', evidence_list: [],
    inspection_requirement: '', inspection_time_range: '', inspectors: [], inspection_place: '',
  },
  inspection: {
    method: '', hardware_device: '', software_tools: [
      { name: 'WinRAR压缩管理软件', version: '6.24' },
      { name: 'Python hashlib', version: '3.11.0' },
    ], process_steps: [],
    result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
}

describe('primary software projection', () => {
  it('marks a complete user edit and derives legacy fields/tools', () => {
    const next = applyPrimarySoftwareEdit(report, 'name', '人工工具')
    const updated = applyPrimarySoftwareEdit(next, 'version', 'V2.0.0')
    expect(updated.inspection.primary_software?.confirmation_status).toBe('confirmed_by_user')
    expect(updated.inspection.result.software_name).toBe('人工工具')
    expect(updated.inspection.result.software_version).toBe('V2.0.0')
    expect(updated.inspection.software_tools[0]).toEqual({ name: '人工工具', version: 'V2.0.0' })
  })

  it('returns to unconfirmed when either required field is cleared', () => {
    const next = applyPrimarySoftwareEdit(report, 'version', '')
    expect(next.inspection.primary_software?.confirmation_status).toBe('unconfirmed')
    expect(next.inspection.result.software_version).toBe('')
    expect(next.inspection.software_tools).toHaveLength(2)
  })

  it('keeps HashMyFiles as a runtime tool alongside legacy Python hashlib', () => {
    const hashReport: InspectionReport = {
      ...report,
      inspection: {
        ...report.inspection,
        software_tools: [
          { name: 'WinRAR压缩管理软件', version: '6.24' },
          { name: 'Python hashlib', version: '3.11.0' },
          { name: 'HashMyFiles', version: '2.51' },
        ],
      },
    }
    const next = applyPrimarySoftwareEdit(hashReport, 'version', '')
    const runtimeNames = next.inspection.software_tools.map(tool => tool.name)
    expect(runtimeNames).toContain('HashMyFiles')
    expect(runtimeNames).toContain('Python hashlib')
    expect(runtimeNames).toContain('WinRAR压缩管理软件')
  })
})
