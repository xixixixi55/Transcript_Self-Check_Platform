/** Shared request fields for the optional local source authorization boundary. */
export interface SourceAuthorizationRequest {
  source_authorization_enabled: boolean
}

export interface CaseSubmissionRequest extends SourceAuthorizationRequest {
  source_path: string
  case_name?: string
  case_summary?: string
  case_number?: string | null
  directory_grant_token?: string
  client_instance_id?: string
  session_id?: string
  local_display_name?: string | null
}

export interface SourceReplacementRequest extends SourceAuthorizationRequest {
  source_path: string
  expected_revision: number
  directory_grant_token?: string
}

/** Legacy directory parsing requests must carry the same explicit mode field. */
export interface ParseReportDirectoryRequest extends SourceAuthorizationRequest {
  report_dir: string
  compress?: boolean
  directory_grant_token?: string
}
