import type { SourceAccessStatus } from '@biji/shared/types'

type ConfirmRisk = (message: string) => boolean

const PENDING_WARNING = [
  '来源复核尚未完成。',
  '确认后仍可导出 Word；归档需要等待来源复核完成。仍要继续导出 Word 吗？',
].join('\n\n')

const RESELECTION_WARNING = [
  '来源已经变化、不可用或需要重新选择。',
  '确认风险后仍可导出 Word；归档需要重新选择来源。仍要继续导出 Word 吗？',
].join('\n\n')

export async function runWithSourceExportRiskConfirmation(
  status: SourceAccessStatus,
  exportAction: () => Promise<boolean>,
  confirmRisk: ConfirmRisk = window.confirm,
): Promise<boolean> {
  const warning = status === 'pending'
    ? PENDING_WARNING
    : status === 'requires_reselection' || status === 'invalid'
      ? RESELECTION_WARNING
      : null
  if (warning && !confirmRisk(warning)) return false
  return exportAction()
}
