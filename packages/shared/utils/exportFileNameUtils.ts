const WINDOWS_INVALID_FILE_NAME_CHARS = /[<>:"/\\|?*]/g

export const DEFAULT_EXPORT_FILE_BASENAME = '检查笔录'

/** 返回浏览器下载使用的默认 Word 文件名。 */
export function getDefaultExportFileName(documentNumber?: string): string {
  return normalizeExportFileName(documentNumber?.trim() || DEFAULT_EXPORT_FILE_BASENAME)
}

/** 将文件名统一为恰好一个 .docx 扩展名。 */
export function normalizeExportFileName(name: string): string {
  const withoutExtension = name.trim().replace(/(?:\.docx)+$/i, '')
  const safeName = withoutExtension.replace(WINDOWS_INVALID_FILE_NAME_CHARS, '_').trim()
  return safeName ? `${safeName}.docx` : ''
}

/** 返回自定义文件名的可读校验错误；返回 null 表示可以导出。 */
export function validateExportFileName(name: string): string | null {
  const trimmed = name.trim()
  if (!trimmed) return '自定义文件名不能为空。'
  if (/[<>:"/\\|?*]/.test(trimmed)) {
    return '文件名不能包含 \\ / : * ? " < > | 等 Windows 非法字符。'
  }
  if (!normalizeExportFileName(trimmed)) return '请输入有效的文件名。'
  return null
}
