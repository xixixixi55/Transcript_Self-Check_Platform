import type { FieldState, FieldSource } from '../types'

export const FIELD_SOURCE_LABELS: Record<FieldSource, string> = {
  report: '报告解析',
  user: '人工修改',
  system_default: '系统默认值',
}

/** 返回审核 UI 的来源文本，不将 UI 颜色泄漏到 Word。 */
export function getFieldSourceLabel(source: FieldSource): string {
  return FIELD_SOURCE_LABELS[source]
}

/** 待确认状态必须始终提供来源颜色的文本替代。 */
export function getFieldConfirmationMessage(state: FieldState): string | null {
  return state.confirmation === 'pending' ? '待人工确认' : null
}
