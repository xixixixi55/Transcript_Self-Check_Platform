import { beforeEach, describe, expect, it } from 'vitest'
import {
  buildParseReportDirectoryRequest,
  buildSourceReplacementRequest,
} from './useSourceAuthorizationRequests'

describe('source authorization request builders', () => {
  beforeEach(() => window.localStorage.clear())

  it('uses the persisted enabled mode for workbench source replacement', () => {
    window.localStorage.setItem('biji.sourceAuthorization.enabled', 'true')

    expect(buildSourceReplacementRequest('C:\\SYNTHETIC\\REPORT', 7)).toEqual({
      source_path: 'C:\\SYNTHETIC\\REPORT',
      expected_revision: 7,
      source_authorization_enabled: true,
    })
  })

  it('carries the persisted mode into legacy directory parse requests', () => {
    expect(buildParseReportDirectoryRequest('C:\\SYNTHETIC\\REPORT', {
      compress: false, directoryGrantToken: 'SYNTHETIC-TOKEN',
    })).toEqual({
      report_dir: 'C:\\SYNTHETIC\\REPORT',
      compress: false,
      directory_grant_token: 'SYNTHETIC-TOKEN',
      source_authorization_enabled: false,
    })
  })
})
