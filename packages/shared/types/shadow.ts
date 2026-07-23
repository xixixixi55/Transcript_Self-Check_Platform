/** Safe comparison DTOs for shadow mode diagnostics. */

export interface ShadowDifference {
  field_path: string
  status: 'mismatch' | 'not_comparable'
  diagnostic_code: string
  source?: string
}

export type ShadowPipelineStatus =
  | 'processing'
  | 'partial'
  | 'matched'
  | 'different'
  | 'not_comparable'
  | 'failed'
  | 'incomplete'

export interface ShadowComparisonResult {
  matched: boolean
  status: 'matched' | 'different' | 'not_comparable'
  stage?: string
  differences: ShadowDifference[]
  diagnostic_codes: string[]
}
