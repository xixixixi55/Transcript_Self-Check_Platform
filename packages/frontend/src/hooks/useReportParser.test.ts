// T020: Hooks test — useReportParser
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createElement } from 'react'
import axios from 'axios'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import type { ParseReportResponse } from '@biji/shared/types'
import {
  normalizeParsedReport, resolveCacheClearError, resolveParseError, useReportParser,
} from './useReportParser'

vi.mock('axios', () => ({
  default: { post: vi.fn(), delete: vi.fn() },
}))

const parsedResponse = {
  report: {
    inspection: { result: { data_summary: '' } },
  },
} as ParseReportResponse

function ParserHarness() {
  const parser = useReportParser()
  return createElement('div', null,
    createElement('button', { onClick: () => void parser.parseReport('SYNTHETIC-REPORT-DIR') }, 'parse'),
    createElement('button', { onClick: () => void parser.clearReportParsingCache() }, 'clear'),
    createElement('span', { 'data-testid': 'parse-loading' }, String(parser.loading)),
    createElement('span', { 'data-testid': 'clear-loading' }, String(parser.clearingCache)),
    createElement('span', { 'data-testid': 'parse-error' }, parser.error),
    createElement('span', { 'data-testid': 'clear-error' }, parser.cacheClearError),
    createElement('span', { 'data-testid': 'clear-message' }, parser.cacheClearMessage),
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

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

  it('exposes a stable authorization code without showing a local path', () => {
    const result = resolveParseError({
      response: {
        data: {
          detail: { code: 'ARCHIVE_INPUT_ROOT_NOT_ALLOWED', message: 'unsafe path' },
        },
      },
    })
    expect(result.code).toBe('ARCHIVE_INPUT_ROOT_NOT_ALLOWED')
    expect(result.message).not.toContain('unsafe path')
  })

  it('maps cache clear failures to a safe actionable message', () => {
    expect(resolveCacheClearError({
      response: { data: { detail: { code: 'REPORT_PARSING_CACHE_CLEAR_FAILED' } } },
    })).toBe('解析缓存清理失败，请重试。')
  })
  it('ends parsing loading and reports a retryable timeout', async () => {
    vi.mocked(axios.post).mockRejectedValueOnce({ code: 'ECONNABORTED' })
    render(createElement(ParserHarness))

    fireEvent.click(screen.getByRole('button', { name: 'parse' }))

    await waitFor(() => expect(screen.getByTestId('parse-loading').textContent).toBe('false'))
    expect(screen.getByTestId('parse-error').textContent).toContain('报告解析请求超时，请重试。')
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/reports/parse', expect.any(FormData),
      expect.objectContaining({ timeout: 120000, signal: expect.any(AbortSignal) }),
    )
  })

  it('ends cache clearing loading and reports an empty-cache success', async () => {
    vi.mocked(axios.delete).mockResolvedValueOnce({
      data: { success: true, data: { cleared_count: 0 } },
    })
    render(createElement(ParserHarness))

    fireEvent.click(screen.getByRole('button', { name: 'clear' }))

    await waitFor(() => expect(screen.getByTestId('clear-loading').textContent).toBe('false'))
    expect(screen.getByTestId('clear-message').textContent).toContain('当前没有可清理的缓存。')
    expect(axios.delete).toHaveBeenCalledWith(
      '/api/v1/cache/report-parsing',
      expect.objectContaining({ timeout: 10000, signal: expect.any(AbortSignal) }),
    )
  })

  it('ends cache clearing loading after a network failure', async () => {
    vi.mocked(axios.delete).mockRejectedValueOnce(new Error('Network Error'))
    render(createElement(ParserHarness))

    fireEvent.click(screen.getByRole('button', { name: 'clear' }))

    await waitFor(() => expect(screen.getByTestId('clear-loading').textContent).toBe('false'))
    expect(screen.getByTestId('clear-error').textContent)
      .toContain('无法连接后端服务，请检查服务状态后重试。')
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
