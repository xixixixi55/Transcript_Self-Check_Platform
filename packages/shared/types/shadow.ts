/** Safe comparison DTOs for shadow mode diagnostics. */

export interface ShadowDifference {
  field_path: string
  status: 'mismatch'
  diagnostic_code: string
}

export interface ShadowComparisonResult {
  matched: boolean
  differences: ShadowDifference[]
  diagnostic_codes: string[]
}
