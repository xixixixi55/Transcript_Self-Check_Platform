import type { ParseReportDirectoryRequest, SourceReplacementRequest } from '@biji/shared/types'
import { getSourceAuthorizationEnabled } from './useSourceAuthorizationPreference'

export function buildSourceReplacementRequest(
  sourcePath: string, expectedRevision: number,
): SourceReplacementRequest {
  return {
    source_path: sourcePath,
    expected_revision: expectedRevision,
    source_authorization_enabled: getSourceAuthorizationEnabled(),
  }
}

export function buildParseReportDirectoryRequest(
  reportDir: string,
  options: { compress?: boolean; directoryGrantToken?: string } = {},
): ParseReportDirectoryRequest {
  return {
    report_dir: reportDir,
    compress: options.compress ?? true,
    directory_grant_token: options.directoryGrantToken,
    source_authorization_enabled: getSourceAuthorizationEnabled(),
  }
}
