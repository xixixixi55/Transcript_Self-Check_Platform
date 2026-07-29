import {
  WINDOWS_INVALID_FILE_NAME_CHARS,
  getDefaultWordDownloadName,
  normalizeWordDownloadName,
  validateWordDownloadName,
} from './downloadFileName'

export const DEFAULT_EXPORT_FILE_BASENAME = '检查笔录'

/** 返回浏览器下载使用的默认 Word 文件名。 */
export function getDefaultExportFileName(documentNumber?: string): string {
  return getDefaultWordDownloadName(documentNumber) || `${DEFAULT_EXPORT_FILE_BASENAME}.docx`
}

/** 将文件名统一为恰好一个 .docx 扩展名。 */
export function normalizeExportFileName(name: string): string {
  return normalizeWordDownloadName(name.replace(WINDOWS_INVALID_FILE_NAME_CHARS, '_'))
}

/** 返回自定义文件名的可读校验错误；返回 null 表示可以导出。 */
export function validateExportFileName(name: string): string | null {
  return validateWordDownloadName(name)
}
