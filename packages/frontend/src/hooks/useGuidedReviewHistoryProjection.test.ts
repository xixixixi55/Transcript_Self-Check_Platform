import type { FieldState, InspectionReport } from '@biji/shared/types'
import { describe, expect, it } from 'vitest'
import { syntheticReport } from './useGuidedReviewCards.testFixtures'
import { buildReportHistory } from './useGuidedReviewHistoryProjection'

function userState(fieldPath: string): FieldState {
  return {
    field_path: fieldPath,
    source: 'user',
    confirmation: 'confirmed',
    revision: 1,
    last_changed_at: '2026-09-03T00:00:00Z',
  }
}

describe('guided Word preview source attribution', () => {
  it('classifies complete and attention IMEI material previews without hiding serial numbers', () => {
    const base = syntheticReport.introduction.evidence_list[0]
    const materials = [
      { ...base, id: 'SYNTHETIC-COMPLETE', evidence_id: 'SYNTHETIC-COMPLETE',
        imei1: '111111111111111', imei2: '222222222222222', serial_number: 'SYNTHETIC-SERIAL-A' },
      { ...base, id: 'SYNTHETIC-MISSING', evidence_id: 'SYNTHETIC-MISSING',
        imei1: '333333333333333', imei2: '', serial_number: 'SYNTHETIC-SERIAL-B' },
      { ...base, id: 'SYNTHETIC-DUPLICATE', evidence_id: 'SYNTHETIC-DUPLICATE',
        imei1: '', imei2: '', serial_number: 'SYNTHETIC-SERIAL-C', extractable: undefined },
    ]
    const projected = buildReportHistory({
      ...syntheticReport,
      introduction: { ...syntheticReport.introduction, evidence_list: materials },
    }).find(item => item.id === 'fact-evidence')?.materials || []

    expect(projected.map(item => item.imeiStatus)).toEqual(['complete', 'attention', 'attention'])
    expect(projected[2].fields.find(field => field.label === '提取情况')?.value).toBe('可提取')
    expect(projected[1].fields.find(field => field.label === 'IMEI 2')?.value).toBe('待核对')
    expect(projected.map(item => item.fields.find(field => field.label === '序列号')?.value))
      .toEqual(['SYNTHETIC-SERIAL-A', 'SYNTHETIC-SERIAL-B', 'SYNTHETIC-SERIAL-C'])
  })

  it('explains why a fully populated material still needs attention when both IMEIs match', () => {
    const material = {
      ...syntheticReport.introduction.evidence_list[0],
      device_name: 'SYNTHETIC Phone', material_type: 'phone' as const,
      imei1: 'SYNTHETIC-SAME-IMEI', imei2: 'SYNTHETIC-SAME-IMEI',
    }
    const projected = buildReportHistory({
      ...syntheticReport,
      introduction: { ...syntheticReport.introduction, evidence_list: [material] },
    }).find(item => item.id === 'fact-evidence')?.materials?.[0]

    expect(projected).toEqual(expect.objectContaining({
      imeiStatus: 'attention', attentionReason: 'IMEI1 与 IMEI2 不能相同',
    }))
  })

  it.each([
    { device_name: '', device_type: '', brand: '', model: '' },
    { device_name: ' \t', device_type: ' ', brand: ' ', model: '\n' },
    { material_type: undefined },
    { device_name: '', device_type: '', material_type: undefined },
  ])('flags missing device or type even with distinct IMEIs and clears after correction: %j', missing => {
    const complete = {
      ...syntheticReport.introduction.evidence_list[0],
      device_name: 'SYNTHETIC DEVICE', imei1: '111111111111111', imei2: '222222222222222',
    }
    const report: InspectionReport = {
      ...syntheticReport,
      introduction: { ...syntheticReport.introduction, evidence_list: [{ ...complete, ...missing }] },
    }
    const project = () => buildReportHistory(report).find(item => item.id === 'fact-evidence')?.materials?.[0]
    expect(project()?.imeiStatus).toBe('attention')
    report.introduction.evidence_list[0] = complete
    expect(project()?.imeiStatus).toBe('complete')
  })

  it('does not label evidence-derived result fields as user-filled', () => {
    const report = {
      ...syntheticReport,
      inspection: {
        ...syntheticReport.inspection,
        process_steps: [
          { step_number: 1, content: 'SYNTHETIC/TEST：由检材信息映射生成的检查步骤。' },
        ],
        result: {
          ...syntheticReport.inspection.result,
          evidence_number: 'SYN-JC00000001',
          data_summary: 'SYNTHETIC/TEST：用户直接填写的数据摘要。',
        },
      },
    }
    const history = buildReportHistory(report, {
      'inspection.process_steps': userState('inspection.process_steps'),
      'inspection.result.evidence_number': userState('inspection.result.evidence_number'),
      'inspection.result.data_summary': userState('inspection.result.data_summary'),
    })
    const resultFields = history.find(item => item.id === 'fact-result')?.fields || []

    expect(resultFields.find(field => field.label === '检查步骤 1')?.userProvided).toBeUndefined()
    expect(resultFields.find(field => field.label === '检材编号')?.userProvided).toBeUndefined()
    expect(resultFields.find(field => field.label === '数据摘要')?.userProvided).toBe(true)
  })

  it('labels a user-added material once without repeating the source on every child field', () => {
    const material = {
      ...syntheticReport.introduction.evidence_list[0],
      id: 'local-evidence-SYNTHETIC-1', evidence_id: 'local-evidence-SYNTHETIC-1',
      device_name: 'SYNTHETIC Phone', evidence_number: 'SYN-JC00000003',
      material_type: 'phone' as const, material_type_source: 'user' as const,
      extractable: false, unextractable_reason: 'SYNTHETIC/TEST：设备损坏',
    }
    const prefix = `evidence.${material.evidence_id}.`
    const history = buildReportHistory({
      ...syntheticReport,
      introduction: { ...syntheticReport.introduction, evidence_list: [material] },
    }, Object.fromEntries(['device_name', 'material_type', 'extractable', 'unextractable_reason']
      .map(field => [`${prefix}${field}`, userState(`${prefix}${field}`)])))
    const projected = history.find(item => item.id === 'fact-evidence')?.materials?.[0]

    expect(projected).toEqual(expect.objectContaining({ userProvided: true, sourceLabel: '人工添加' }))
    expect(projected?.fields.every(field => !field.userProvided && !field.sourceLabel)).toBe(true)
  })

  it('labels only the edited field on a recognized material', () => {
    const material = {
      ...syntheticReport.introduction.evidence_list[0],
      id: 'SYNTHETIC-RECOGNIZED', evidence_id: 'SYNTHETIC-RECOGNIZED',
      device_name: 'SYNTHETIC Edited Phone', evidence_number: 'SYN-JC00000001',
      material_type: 'phone' as const, material_type_source: 'report' as const,
    }
    const modelPath = `evidence.${material.evidence_id}.device_name`
    const history = buildReportHistory({
      ...syntheticReport,
      introduction: { ...syntheticReport.introduction, evidence_list: [material] },
    }, { [modelPath]: userState(modelPath) })
    const projected = history.find(item => item.id === 'fact-evidence')?.materials?.[0]

    expect(projected?.userProvided).toBeUndefined()
    expect(projected?.fields.find(field => field.label === '设备'))
      .toEqual(expect.objectContaining({ userProvided: true, sourceLabel: '已修改' }))
    expect(projected?.fields.filter(field => field.userProvided)).toHaveLength(1)
  })

  it('projects an optional holder without changing material completeness', () => {
    const material = {
      ...syntheticReport.introduction.evidence_list[0],
      id: 'SYNTHETIC-HOLDER-MATERIAL', evidence_id: 'SYNTHETIC-HOLDER-MATERIAL',
      device_name: 'SYNTHETIC Phone', material_type: 'phone' as const,
      imei1: '111111111111111', imei2: '222222222222222',
      holder_name: '',
    }
    const holderPath = `evidence.${material.evidence_id}.holder_name`
    const project = (holderName: string, fieldStates = {}) => buildReportHistory({
      ...syntheticReport,
      introduction: {
        ...syntheticReport.introduction,
        evidence_list: [{ ...material, holder_name: holderName }],
      },
    }, fieldStates).find(item => item.id === 'fact-evidence')?.materials?.[0]

    expect(project('')?.imeiStatus).toBe('complete')
    expect(project('')?.fields.find(field => field.label === '持有人')?.value).toBe('未填写')
    expect(project('SYNTHETIC-HOLDER-A', { [holderPath]: userState(holderPath) })?.fields
      .find(field => field.label === '持有人'))
      .toEqual(expect.objectContaining({ value: 'SYNTHETIC-HOLDER-A', userProvided: true, sourceLabel: '已修改' }))
  })
})
