/** 本机报告目录登记和解析请求。 */
export interface CaseSubmissionRequest {
  source_path: string
  case_name?: string
  case_summary?: string
  case_number?: string | null
  client_instance_id?: string
  session_id?: string
  local_display_name?: string | null
}

/** 可信本地 Windows 目录选择器桥接使用的无路径请求。 */
export interface CaseDirectorySubmissionRequest {
  case_name?: string
  case_summary?: string
  case_number?: string | null
  client_instance_id?: string
  session_id?: string
  local_display_name?: string | null
}

export interface SourceReplacementRequest {
  source_path: string
  expected_revision: number
}

/** 旧版目录解析请求。 */
export interface ParseReportDirectoryRequest {
  report_dir: string
  compress?: boolean
}
