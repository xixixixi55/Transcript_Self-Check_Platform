export type DiscSequenceErrorCode =
  | 'FIRST_DISC_NUMBER_MISSING'
  | 'FIRST_DISC_NUMBER_INVALID'
  | 'FIRST_DISC_DATE_INVALID'
  | 'FIRST_DISC_SEQUENCE_INVALID'

export interface DiscSequence {
  prefix: string
  date: string
  /** 新 GP/YP 标识中的两位用户标记；旧版值中不存在。 */
  user_identifier?: string
  start_number: number
  number_width: number
  first_disc_number: string
}

export interface DiscSequenceParseResult {
  valid: boolean
  sequence?: DiscSequence
  error_code?: DiscSequenceErrorCode
}
