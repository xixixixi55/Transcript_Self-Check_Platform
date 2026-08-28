/** 可选本地来源授权边界的共享请求字段。 */
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

/** 可信本地 Windows 目录选择器桥接使用的无路径请求。 */
export interface CaseDirectorySubmissionRequest extends SourceAuthorizationRequest {
  case_name?: string
  case_summary?: string
  case_number?: string | null
  client_instance_id?: string
  session_id?: string
  local_display_name?: string | null
}

export interface SourceReplacementRequest extends SourceAuthorizationRequest {
  source_path: string
  expected_revision: number
  directory_grant_token?: string
}

/** 旧版目录解析请求必须携带相同的显式模式字段。 */
export interface ParseReportDirectoryRequest extends SourceAuthorizationRequest {
  report_dir: string
  compress?: boolean
  directory_grant_token?: string
}
