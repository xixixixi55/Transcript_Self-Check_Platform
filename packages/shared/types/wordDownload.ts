/**
 * A user-facing Word download name. It deliberately excludes the server's
 * physical artifact name, which is generated independently and never exposed
 * through this DTO.
 */
export interface WordDownloadName {
  download_name: string
}
