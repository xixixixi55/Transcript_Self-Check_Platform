import { beforeEach, describe, expect, it } from 'vitest'
import {
  buildParseReportDirectoryRequest,
  buildSourceReplacementRequest,
} from './useSourceRequests'

describe('source request builders', () => {
  beforeEach(() => window.localStorage.clear())

  it('ignores the retired preference when replacing a source', () => {
    window.localStorage.setItem('biji.sourceAuthorization.enabled', 'true')

    expect(buildSourceReplacementRequest('C:\\SYNTHETIC\\REPORT', 7)).toEqual({
      source_path: 'C:\\SYNTHETIC\\REPORT',
      expected_revision: 7,
    })
  })

  it('builds legacy parse requests without authorization fields', () => {
    expect(buildParseReportDirectoryRequest('C:\\SYNTHETIC\\REPORT', {
      compress: false,
    })).toEqual({
      report_dir: 'C:\\SYNTHETIC\\REPORT',
      compress: false,
    })
  })
})
