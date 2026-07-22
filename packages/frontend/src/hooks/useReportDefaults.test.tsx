import React from 'react'
import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import type { InspectionReport } from '@biji/shared/types'
import { useReportDefaults } from './useReportDefaults'

const report = (): InspectionReport => ({
  title: '测试', document_number: 'DOC', introduction: {
    entrust_unit: '', entrust_persons: [], entrust_time: '', case_summary: '', evidence_list: [],
    inspection_requirement: '', inspection_time_range: '', inspectors: [], inspection_place: '地点',
    inspector_snapshots: [{ inspector_id: 'one', name: '甲', unit: '单位', police_number: '001' }],
  }, inspection: { method: '方法', hardware_device: '硬件', software_tools: [], process_steps: [],
    result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' } },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: 'GP20260718-001' },
})

describe('useReportDefaults', () => {
  beforeEach(() => window.localStorage.clear())

  it('persists and reapplies all six initial default fields', () => {
    const { result } = renderHook(() => useReportDefaults())
    act(() => result.current.saveDiscPrefix('测试公'))
    act(() => result.current.saveCurrentReport(report()))
    const next = result.current.applyDefaults({ ...report(), document_number: 'OTHER' })
    expect(next.document_number).toBe('DOC')
    expect(next.introduction.inspection_place).toBe('地点')
    expect(next.inspection.method).toBe('方法')
    expect(next.inspection.hardware_device).toBe('硬件')
    expect(next.introduction.inspector_snapshots?.[0].name).toBe('甲')
    expect(next.attachments.disc_number).toBe('测试公20260718-001')
  })

  it('clears every saved default', () => {
    const { result } = renderHook(() => useReportDefaults())
    act(() => result.current.saveCurrentReport(report()))
    act(() => result.current.clearDefaults())
    expect(result.current.defaults.document_number).toBe('')
    expect(result.current.defaults.inspector_snapshots).toEqual([])
  })
})
