import type { ParseReportDirectoryRequest, SourceReplacementRequest } from '@biji/shared/types'

export function buildSourceReplacementRequest(
  sourcePath: string, expectedRevision: number,
): SourceReplacementRequest {
  return {
    source_path: sourcePath,
    expected_revision: expectedRevision,
  }
}

export function buildParseReportDirectoryRequest(
  reportDir: string,
  options: { compress?: boolean } = {},
): ParseReportDirectoryRequest {
  return {
    report_dir: reportDir,
    compress: options.compress ?? true,
  }
}
