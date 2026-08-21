export interface ArchiveStorageSettings {
  active_directory: string
  configured_directory: string
  default_directory: string
  custom: boolean
  valid: boolean
  restart_required: boolean
  error_code: string | null
}
