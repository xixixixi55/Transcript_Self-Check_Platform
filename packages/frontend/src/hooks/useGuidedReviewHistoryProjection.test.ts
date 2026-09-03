import type { FieldState } from '@biji/shared/types'
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
})
