// T020: Hooks test — useReportParser
import { describe, it, expect } from 'vitest'
import type { ParseReportResponse } from '@biji/shared/types'
import { normalizeParsedReport } from './useReportParser'

const parsedResponse = {
  report: {
    inspection: { result: { data_summary: '' } },
  },
} as ParseReportResponse

describe('normalizeParsedReport', () => {
  it('normalizes a missing or blank summary before page state is set', () => {
    expect(normalizeParsedReport(parsedResponse).report.inspection.result.data_summary)
      .toBe('即时通讯、手机信息')
  })

  it('preserves a non-empty summary', () => {
    const response = JSON.parse(JSON.stringify(parsedResponse)) as ParseReportResponse
    response.report.inspection.result.data_summary = '用户自定义摘要'
    expect(normalizeParsedReport(response).report.inspection.result.data_summary)
      .toBe('用户自定义摘要')
  })
})

// Test that hooks export correctly (full testing requires component mounting)
describe('useReportParser', () => {
  it('should be importable', async () => {
    const mod = await import('./useReportParser')
    expect(mod.useReportParser).toBeDefined()
    expect(typeof mod.useReportParser).toBe('function')
  })
})

describe('useRecordExport', () => {
  it('should be importable', async () => {
    const mod = await import('./useRecordExport')
    expect(mod.useRecordExport).toBeDefined()
    expect(typeof mod.useRecordExport).toBe('function')
  })

  it('uses the default name unless a custom name is explicitly supplied', async () => {
    const { resolveExportFileName } = await import('./useRecordExport')
    expect(resolveExportFileName('SYN-TEST〔2026〕200号')).toBe('SYN-TEST〔2026〕200号.docx')
    expect(resolveExportFileName('SYN-TEST〔2026〕200号', '自定义名称.docx.docx')).toBe('自定义名称.docx')
  })
})
