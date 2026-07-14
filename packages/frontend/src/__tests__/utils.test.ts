// T004: Shared 层工具函数测试
import { describe, it, expect } from 'vitest'
import { generateDocumentNumber, formatFileSize, formatTimeRange, sanitizeFileName } from '@biji/shared/utils'

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
