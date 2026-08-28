import type { WordDownloadName } from '../types'

export const WINDOWS_INVALID_FILE_NAME_CHARS = /[<>:"/\\|?*]/g
const WINDOWS_INVALID_FILE_NAME_PATTERN = /[<>:"/\\|?*]/

/** 返回阶段 2 默认值：当前文书编号，或空名称。 */
export function getDefaultWordDownloadName(documentNumber?: string): string {
  return normalizeWordDownloadName(documentNumber || '')
}

/** 将有效基本名称规范化为恰好一个 .docx 扩展名。 */
export function normalizeWordDownloadName(name: string): string {
  const baseName = name.trim().replace(/(?:\.docx)+$/i, '').trim()
  return baseName ? `${baseName}.docx` : ''
}

/** 为无效的用户侧 Word 下载名称返回可读错误。 */
export function validateWordDownloadName(name: string): string | null {
  if (!name.trim()) return '自定义文件名不能为空。'
  if (WINDOWS_INVALID_FILE_NAME_PATTERN.test(name)) {
    return '文件名不能包含 \\ / : * ? " < > | 等 Windows 非法字符。'
  }
  return normalizeWordDownloadName(name) ? null : '请输入有效的文件名。'
}

/** 仅在验证成功后构建公开下载名称 DTO。 */
export function toWordDownloadName(name: string): WordDownloadName | null {
  if (validateWordDownloadName(name)) return null
  return { download_name: normalizeWordDownloadName(name) }
}
