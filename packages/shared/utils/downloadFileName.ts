import type { WordDownloadName } from '../types'

export const WINDOWS_INVALID_FILE_NAME_CHARS = /[<>:"/\\|?*]/g
const WINDOWS_INVALID_FILE_NAME_PATTERN = /[<>:"/\\|?*]/

/** Returns the Phase 2 default: the current document number, or an empty name. */
export function getDefaultWordDownloadName(documentNumber?: string): string {
  return normalizeWordDownloadName(documentNumber || '')
}

/** Normalizes a valid basename to exactly one .docx extension. */
export function normalizeWordDownloadName(name: string): string {
  const baseName = name.trim().replace(/(?:\.docx)+$/i, '').trim()
  return baseName ? `${baseName}.docx` : ''
}

/** Returns a readable error for an invalid user-facing Word download name. */
export function validateWordDownloadName(name: string): string | null {
  if (!name.trim()) return '自定义文件名不能为空。'
  if (WINDOWS_INVALID_FILE_NAME_PATTERN.test(name)) {
    return '文件名不能包含 \\ / : * ? " < > | 等 Windows 非法字符。'
  }
  return normalizeWordDownloadName(name) ? null : '请输入有效的文件名。'
}

/** Builds the public download-name DTO only after validation succeeds. */
export function toWordDownloadName(name: string): WordDownloadName | null {
  if (validateWordDownloadName(name)) return null
  return { download_name: normalizeWordDownloadName(name) }
}
