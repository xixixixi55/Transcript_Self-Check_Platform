import type { InspectionReport } from '@biji/shared/types'
import { describe, expect, it } from 'vitest'
import { getReviewPendingItems } from './useReviewChecklist'

const report: InspectionReport = {
  title: '电子数据检查笔录', document_number: '', case_number: '2026-001',
  introduction: {
    entrust_unit: '', entrust_persons: [], entrust_time: '2026年2月30日', case_summary: '',
    evidence_list: [], inspection_requirement: '', inspection_time_range: '', inspectors: [], inspection_place: '',
  },
  inspection: {
    method: '', hardware_device: '', software_tools: [], process_steps: [],
    result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
}

describe('getReviewPendingItems', () => {
  it('只根据实际空缺字段和既有格式校验生成清单', () => {
    const items = getReviewPendingItems(report)
    expect(items.length).toBeGreaterThan(0)
    expect(items.some(item => item.fieldLabel === '委托时间' && item.severity === 'error')).toBe(true)
    expect(items.some(item => item.fieldLabel === '案件简要情况' && item.severity === 'warning')).toBe(true)
  })

  it('接收已有文件名校验错误而不编造数量', () => {
    const items = getReviewPendingItems({ ...report, document_number: '文号' }, '文件名格式错误')
    expect(items.some(item => item.fieldLabel === '导出文件名' && item.reason === '文件名格式错误')).toBe(true)
  })

  it('未确认检材类型时生成导出阻断提示', () => {
    const items = getReviewPendingItems({
      ...report,
      introduction: {
        ...report.introduction,
        evidence_list: [{
          id: 'material-1', device_type: '合成设备', evidence_number: 'E-1',
          material_type: 'unconfirmed', material_type_status: 'unconfirmed',
        }],
      },
    })
    expect(items.some(item => item.fieldLabel === '检材1类型' && item.severity === 'error')).toBe(true)
  })

  it('确认状态缺少合法来源时仍生成导出阻断提示', () => {
    const items = getReviewPendingItems({
      ...report,
      introduction: {
        ...report.introduction,
        evidence_list: [{
          id: 'material-1', device_type: '手机', evidence_number: 'E-1',
          material_type: 'phone', material_type_status: 'confirmed_by_report', material_type_source: 'none',
        }],
      },
    })
    expect(items.some(item => item.fieldLabel === '检材1类型' && item.severity === 'error')).toBe(true)
  })
})
