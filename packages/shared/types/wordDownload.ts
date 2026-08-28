/**
 * 面向用户的 Word 下载名称。它有意排除服务器的物理工件名称；
 * 后者独立生成，绝不通过此 DTO 公开。
 */
export interface WordDownloadName {
  download_name: string
}

/** 单独导出 Word 后返回的、经选择器授权的输出。 */
export interface WordDirectoryExportResult {
  export_path: string
  word_filename: string
  warnings?: WordExportWarning[]
}

export interface WordExportWarning {
  code: string
  message: string
}

/** 附加到单独 Word 导出请求的目录授权字段。 */
export interface WordDirectoryExportTarget {
  path: string
  token: string
}
