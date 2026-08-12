import type { InspectionReport } from '@biji/shared/types'
import { describe, expect, it } from 'vitest'
import { getReviewPendingItems, REVIEW_SECTION_IDS, REVIEW_TARGET_IDS } from './useReviewChecklist'

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

  it('为不同字段生成稳定且可区分的精确目标', () => {
    const items = getReviewPendingItems(report)
    expect(items.find(item => item.fieldLabel === '文号')?.targetId).toBe(REVIEW_TARGET_IDS.documentNumber)
    expect(items.find(item => item.fieldLabel === '案件简要情况')?.targetId).toBe(REVIEW_TARGET_IDS.caseSummary)
    expect(items.find(item => item.fieldLabel === 'RAR 文件名')?.targetId).toBe(REVIEW_TARGET_IDS.result('rar_filename'))
    expect(items.find(item => item.fieldLabel === 'MD5 哈希')?.targetId).toBe(REVIEW_TARGET_IDS.result('md5_hash'))
  })

  it.each(['', 'INVALID-DISC'])('光盘编号“%s”始终指向顶部首个盘号输入', discNumber => {
    const items = getReviewPendingItems({
      ...report,
      attachments: { ...report.attachments, disc_number: discNumber },
    })
    const discItems = items.filter(item => item.fieldLabel === '光盘编号')
    expect(discItems.length).toBeGreaterThan(0)
    expect(discItems.every(item => item.targetId === REVIEW_TARGET_IDS.discNumber)).toBe(true)
    expect(discItems.every(item => item.sectionId === REVIEW_SECTION_IDS.archive)).toBe(true)
  })
})
