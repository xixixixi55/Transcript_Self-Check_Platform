import React from 'react'
import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { InspectionReport } from '@biji/shared/types'
import { useCaseExportSettings } from './useCaseExportSettings'

const report: InspectionReport = {
  title: 'SYNTHETIC/TEST record', document_number: 'SYNTHETIC-DOC',
  introduction: {
    entrust_unit: '', entrust_persons: [], entrust_time: '', case_summary: '', evidence_list: [],
    inspection_requirement: '', inspection_time_range: '', inspectors: [], inspection_place: '',
  },
  inspection: {
    method: '', hardware_device: '', software_tools: [], process_steps: [],
    result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
}

describe('useCaseExportSettings', () => {
  it('keeps default and custom export names separate and validates custom input', () => {
    const { result } = renderHook(() => useCaseExportSettings(report))
    expect(result.current.requestedFileName).toContain('SYNTHETIC-DOC')
    act(() => result.current.setCustomFileName(true))
    act(() => result.current.setFileName('SYNTHETIC-CUSTOM'))
    expect(result.current.requestedFileName).toBe('SYNTHETIC-CUSTOM')
    expect(result.current.validate()).toBeNull()
  })
})
