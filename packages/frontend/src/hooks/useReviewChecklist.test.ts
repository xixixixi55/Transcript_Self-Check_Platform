import type { InspectionReport } from '@biji/shared/types'
import { describe, expect, it } from 'vitest'
import {
  getReviewPendingItems,
  getReviewProgressSectionItems,
  REVIEW_SECTION_IDS,
  REVIEW_TARGET_IDS,
} from './useReviewChecklist'

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
    expect(items.some(item => item.fieldLabel === '案件简要情况'
      && item.severity === 'warning' && item.kind === 'required_missing')).toBe(true)
    expect(items.some(item => item.fieldLabel === '委托时间'
      && item.severity === 'error' && item.kind === 'validation')).toBe(true)
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

  it('人工检材确认类型后不再保留旧设备类型待核对项', () => {
    const items = getReviewPendingItems({
      ...report,
      introduction: {
        ...report.introduction,
        evidence_list: [{
          id: 'material-synthetic-manual', device_type: '', device_name: '', model: '',
          evidence_number: 'SYN-MANUAL-3', material_type: 'phone',
          material_type_status: 'confirmed_by_user', material_type_source: 'user',
        }],
      },
    })

    expect(items.some(item => item.fieldLabel === '检材1设备类型')).toBe(false)
    expect(items.some(item => item.fieldLabel === '检材1类型')).toBe(false)
  })

  it.each([
    ['phone', '手机'],
    ['tablet', '平板'],
  ] as const)('人工确认 %s 时将确认值作为有效设备语义', (materialType, _label) => {
    const items = getReviewPendingItems({
      ...report,
      introduction: {
        ...report.introduction,
        evidence_list: [{
          id: 'material-synthetic-confirmed', device_type: '', evidence_number: 'SYN-CONFIRMED',
          material_type: materialType, material_type_status: 'confirmed_by_user', material_type_source: 'user',
        }],
      },
    })
    expect(items.some(item => item.fieldLabel.startsWith('检材1'))).toBe(false)
  })

  it('人工确认状态的来源非法时仍保留类型阻断', () => {
    const items = getReviewPendingItems({
      ...report,
      introduction: {
        ...report.introduction,
        evidence_list: [{
          id: 'material-synthetic-invalid-source', device_type: '', evidence_number: 'SYN-INVALID',
          material_type: 'phone', material_type_status: 'confirmed_by_user', material_type_source: 'none',
        }],
      },
    })
    expect(items.some(item => item.fieldLabel === '检材1类型' && item.severity === 'error')).toBe(true)
  })

  it('报告确认类型但没有设备语义时仍保留设备类型提示', () => {
    const items = getReviewPendingItems({
      ...report,
      introduction: {
        ...report.introduction,
        evidence_list: [{
          id: 'material-synthetic-report', device_type: '', evidence_number: 'SYN-REPORT',
          material_type: 'phone', material_type_status: 'confirmed_by_report', material_type_source: 'report',
        }],
      },
    })
    expect(items.some(item => item.fieldLabel === '检材1设备类型')).toBe(true)
    expect(items.some(item => item.fieldLabel === '检材1类型')).toBe(false)
  })

  it('未确认类型但已有设备名称时只保留类型阻断', () => {
    const items = getReviewPendingItems({
      ...report,
      introduction: {
        ...report.introduction,
        evidence_list: [{
          id: 'material-synthetic-named', device_type: '', device_name: 'SYNTHETIC PHONE',
          evidence_number: 'SYN-NAMED', material_type: 'unconfirmed', material_type_status: 'unconfirmed',
        }],
      },
    })
    expect(items.some(item => item.fieldLabel === '检材1设备类型')).toBe(false)
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
    expect(getReviewProgressSectionItems(items, REVIEW_SECTION_IDS.attachments)).toEqual(
      expect.arrayContaining(discItems),
    )
  })

  it('按归档介质区分 GP 与 YP 编号校验', () => {
    const withNumber = (discNumber: string) => ({
      ...report,
      attachments: { ...report.attachments, disc_number: discNumber },
    })

    expect(getReviewPendingItems(withNumber('YP20260820-01'), undefined, 'hard_drive')
      .some(item => item.fieldLabel === '硬盘编号' && item.kind === 'validation')).toBe(false)
    expect(getReviewPendingItems(withNumber('GP20260820-01'), undefined, 'hard_drive')
      .some(item => item.reason.includes('YPyyyyMMdd-序号'))).toBe(true)
    expect(getReviewPendingItems(withNumber('YP20260820-01'), undefined, 'optical_disc')
      .some(item => item.reason.includes('GPyyyyMMdd-序号'))).toBe(true)
    expect(getReviewPendingItems(withNumber('YP20260820-01'), undefined, null)
      .some(item => item.kind === 'validation' && item.targetId === REVIEW_TARGET_IDS.discNumber)).toBe(false)
    expect(getReviewPendingItems(withNumber('AB20260820-01'), undefined, null)
      .some(item => item.reason.includes('GPyyyyMMdd-序号 或 YPyyyyMMdd-序号'))).toBe(true)
  })
})
