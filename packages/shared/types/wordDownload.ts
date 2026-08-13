/**
 * A user-facing Word download name. It deliberately excludes the server's
 * physical artifact name, which is generated independently and never exposed
 * through this DTO.
 */
export interface WordDownloadName {
  download_name: string
}

/** Picker-authorized output returned after a standalone Word export. */
export interface WordDirectoryExportResult {
  export_path: string
  word_filename: string
}

/** Directory authorization fields appended to a standalone Word export request. */
export interface WordDirectoryExportTarget {
  path: string
  token: string
}
