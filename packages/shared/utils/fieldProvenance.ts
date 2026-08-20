import type { FieldState, FieldSource } from '../types'

export const FIELD_SOURCE_LABELS: Record<FieldSource, string> = {
  report: '报告解析',
  user: '人工修改',
  system_default: '系统默认值',
}

/** Returns source text for the review UI without leaking UI colors into Word. */
export function getFieldSourceLabel(source: FieldSource): string {
  return FIELD_SOURCE_LABELS[source]
}

/** Pending confirmation must always have a text alternative to source color. */
export function getFieldConfirmationMessage(state: FieldState): string | null {
  return state.confirmation === 'pending' ? '待人工确认' : null
}
