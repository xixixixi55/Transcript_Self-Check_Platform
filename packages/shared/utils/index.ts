// Layer 2: SharedUtils — 前后端共享的纯函数工具
import { DEFAULT_DATA_SUMMARY } from '../constants'
export * from './exportFileNameUtils'
export * from './downloadFileName'
export * from './fieldProvenance'
export * from './naturalEvidenceOrder'
export * from './materialPhotoGroups'
export * from './dateTimeUtils'
export * from './discSequenceUtils'
export * from './softwareProjectionUtils'
export * from './workbenchRules'
export * from './archiveTaskRules'
export * from './archivePlanRules'
export * from './archiveCompletionRules'
export * from './retentionRules'

/** 验证是否为有效的 ISO 8601 日期字符串 */
export function isValidISODate(str: string): boolean {
  const date = new Date(str)
  return date instanceof Date && !isNaN(date.getTime()) && str === date.toISOString()
}

/** 验证 UUID 格式 */
export function isValidUUID(str: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
  return uuidRegex.test(str)
}

/** 驼峰转下划线（TypeScript ↔ Python 字段名转换） */
export function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

/** 下划线转驼峰（Python → TypeScript 字段名转换） */
export function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

/** 获取安全的文件名（移除不安全字符） */
export function sanitizeFileName(name: string): string {
  return name.replace(/[<>:"/\\|?*]/g, '_').trim()
}

/**
 * 生成检查笔录文号
 * 格式: XX电检〔YYYY〕XXXXXX号
 * @param caseNumber 案件编号（如 A0000000000000000000000）
 * @param year 年份，默认当前年份
 * @param prefix 前缀（如 "测试公"），默认 "xx"
 */
export function generateDocumentNumber(caseNumber: string, year?: number, prefix: string = 'xx'): string {
  const y = year ?? new Date().getFullYear()
  // 取案件编号后 6 位数字作为文号后缀
  const digits = caseNumber.replace(/\D/g, '')
  const suffix = digits.slice(-6) || caseNumber.slice(-6)
  return `${prefix}电检〔${y}〕${suffix}号`
}

/**
 * 格式化取证时间范围为检查起止时间
 * 输入: "2026-07-07 16:00:22 ~ 2026-07-07 16:05:39"
 * 输出: "2026年7月7日10点02分至2026年7月7日11点27分"
 */
export function formatTimeRange(timeRange: string): string {
  const parts = timeRange.split(' ~ ')
  if (parts.length !== 2) return timeRange
  return `${formatDateTime(parts[0])}至${formatDateTime(parts[1])}`
}

/** 格式化日期时间为中文格式 */
function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr.replace(' ', 'T'))
  if (isNaN(d.getTime())) return dateStr
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日${d.getHours()}点${pad(d.getMinutes())}分`
}

/** 补零 */
function pad(n: number): string {
  return n < 10 ? `0${n}` : `${n}`
}

/**
 * 根据设备数量和数据分类统计生成数据摘要
 * 如: "即时通讯、手机信息"
 */
export function normalizeDataSummary(value: unknown): string {
  const normalized = typeof value === 'string' ? value.trim() : ''
  return normalized || DEFAULT_DATA_SUMMARY
}

/** 数据分类导航不属于用户编辑的摘要字段，默认摘要固定为甲方要求值。 */
export function generateDataSummary(_categories: string[]): string {
  return DEFAULT_DATA_SUMMARY
}

/**
 * 格式化字节数为可读大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} 字节`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}
