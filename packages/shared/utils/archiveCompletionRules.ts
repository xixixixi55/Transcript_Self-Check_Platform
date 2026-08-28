// 第 2 层：SharedUtils — 归档完成状态投影（纯函数）。

import {
  UNIFIED_EXPORT_HDD_MIN_THROUGHPUT_BYTES_PER_SECOND,
  UNIFIED_EXPORT_MAX_REQUEST_TIMEOUT_MS,
  UNIFIED_EXPORT_ORCHESTRATION_GRACE_MS,
  UNIFIED_EXPORT_REQUEST_TIMEOUT_MS,
} from '../constants'
import type { ArchiveCompletionStatus, CaseLifecycle } from '../types'

/**
 * 根据生命周期以及每个 RAR 分卷是否带有光盘编号，
 * 投影卡片级归档完成状态。其本身不是生命周期值。
 */
export function resolveArchiveCompletionStatus(
  lifecycle: CaseLifecycle,
  allDiscMapped: boolean,
): ArchiveCompletionStatus | null {
  if (lifecycle === 'exported') return 'exported'
  if (lifecycle === 'archive_verified') {
    return allDiscMapped ? 'archive_complete' : 'disc_pending'
  }
  if (lifecycle === 'archiving' || lifecycle === 'archive_queued') return 'compressing'
  return null
}

/** 每个分卷都带有非空光盘编号时返回 true。 */
export function allPartsDiscMapped(
  parts: { disc_number?: string | null }[] | null | undefined,
): boolean {
  return !!parts && parts.length > 0 && parts.every(part => !!part.disc_number)
}

/** 汇总已验证分卷大小；证据不完整时返回 null。 */
export function archivePartsTotalBytes(
  parts: { size_bytes?: number | null }[] | null | undefined,
): number | null {
  if (!parts?.length) return null
  let total = 0
  for (const part of parts) {
    const size = part.size_bytes
    if (typeof size !== 'number' || !Number.isSafeInteger(size) || size <= 0) return null
    total += size
  }
  return Number.isSafeInteger(total) && total > 0 ? total : null
}

/**
 * 将同步导出请求限制在一次 HDD 暂存复制加编排余量内。
 * HashMyFiles 不属于检查笔录导出流程。
 */
export function unifiedExportRequestTimeoutMs(
  totalArchiveBytes: number | null | undefined,
): number {
  if (
    typeof totalArchiveBytes !== 'number'
    || !Number.isSafeInteger(totalArchiveBytes)
    || totalArchiveBytes <= 0
  ) return UNIFIED_EXPORT_REQUEST_TIMEOUT_MS
  const copyPassMilliseconds = Math.ceil(
    (totalArchiveBytes * 1000)
    / UNIFIED_EXPORT_HDD_MIN_THROUGHPUT_BYTES_PER_SECOND,
  )
  return Math.min(
    UNIFIED_EXPORT_MAX_REQUEST_TIMEOUT_MS,
    Math.max(
      UNIFIED_EXPORT_REQUEST_TIMEOUT_MS,
      copyPassMilliseconds
        + UNIFIED_EXPORT_ORCHESTRATION_GRACE_MS,
    ),
  )
}
