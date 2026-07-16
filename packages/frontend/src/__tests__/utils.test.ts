// T004: Shared 层工具函数测试
import { describe, it, expect } from 'vitest'
import {
  fromDateInputValue,
  fromDateTimeRangeInputValues,
  generateDocumentNumber,
  getDefaultExportFileName,
  formatFileSize,
  formatTimeRange,
  isValidDateFieldValue,
  isValidMinuteTimeRangeValue,
  normalizeExportFileName,
  normalizeDataSummary,
  sanitizeFileName,
  toDateInputValue,
  toDateTimeRangeInputValues,
  validateExportFileName,
} from '@biji/shared/utils'

describe('export file name controls', () => {
  it('keeps the current document number as the default download name', () => {
    expect(getDefaultExportFileName('SYN-TEST〔2026〕200号')).toBe('SYN-TEST〔2026〕200号.docx')
  })

  it('normalizes the extension without producing duplicates', () => {
    expect(normalizeExportFileName('  检查结果.docx.docx ')).toBe('检查结果.docx')
    expect(validateExportFileName('')).toBe('自定义文件名不能为空。')
    expect(validateExportFileName('   ')).toBe('自定义文件名不能为空。')
    expect(validateExportFileName('结果/附件')).toContain('Windows 非法字符')
    expect(validateExportFileName('检查结果.docx')).toBeNull()
  })
})

describe('normalizeDataSummary', () => {
  it.each([undefined, null, '', '   '])('uses the fixed default for %j', value => {
    expect(normalizeDataSummary(value)).toBe('即时通讯、手机信息')
  })

  it('preserves a non-empty user value after trimming', () => {
    expect(normalizeDataSummary('  通讯录  ')).toBe('通讯录')
  })
})

describe('generateDocumentNumber', () => {
  it('should generate correct format', () => {
    const result = generateDocumentNumber('A0000000000000000000000', 2026)
    expect(result).toMatch(/xx电检〔2026〕\d+号/)
  })

  it('should use last 6 digits of case number', () => {
    const result = generateDocumentNumber('A0000000000000000000000', 2026)
    expect(result).toBe('xx电检〔2026〕000000号')
  })

  it('should use current year when not specified', () => {
    const result = generateDocumentNumber('TEST000001')
    const year = new Date().getFullYear()
    expect(result).toContain(String(year))
  })
})

describe('formatFileSize', () => {
  it('should format bytes', () => {
    expect(formatFileSize(100)).toBe('100 字节')
  })

  it('should format KB', () => {
    expect(formatFileSize(1024)).toBe('1.0 KB')
  })

  it('should format MB', () => {
    expect(formatFileSize(1024 * 1024)).toBe('1.0 MB')
  })

  it('should format GB', () => {
    expect(formatFileSize(1024 * 1024 * 1024)).toBe('1.0 GB')
  })
})

describe('formatTimeRange', () => {
  it('should return original if no tilde separator', () => {
    expect(formatTimeRange('2026-07-07')).toBe('2026-07-07')
  })
})

describe('sanitizeFileName', () => {
  it('should remove unsafe characters', () => {
    expect(sanitizeFileName('test<>file.txt')).toBe('test__file.txt')
  })
})

describe('date and time controls', () => {
  it('keeps pure date precision and handles leap years', () => {
    expect(toDateInputValue('2026年7月16日')).toBe('2026-07-16')
    expect(fromDateInputValue('2024-02-29')).toBe('2024年2月29日')
    expect(isValidDateFieldValue('2024年2月29日')).toBe(true)
    expect(isValidDateFieldValue('2023年2月29日')).toBe(false)
  })

  it('keeps minute precision for inspection time ranges', () => {
    const value = '2026年7月16日14点30分至2026年7月16日15点05分'
    expect(toDateTimeRangeInputValues(value)).toEqual({
      start: '2026-07-16T14:30', end: '2026-07-16T15:05',
    })
    expect(fromDateTimeRangeInputValues('2026-07-16T14:30', '2026-07-16T15:05')).toBe(value)
    expect(isValidMinuteTimeRangeValue(value)).toBe(true)
    expect(isValidMinuteTimeRangeValue('2026年7月16日15点05分至2026年7月16日14点30分')).toBe(false)
  })
})
