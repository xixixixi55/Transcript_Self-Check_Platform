// 第 10 层：FE_Hooks — 将后台业务事实投影为獬豸助手系统状态。
import type { ArchiveTaskCardSummary, CaseLifecycle, SourceAccessStatus } from '@biji/shared/types'

export interface GuidedReviewSystemStatus {
  title: string
  detail: string
}

interface GuidedReviewSystemStatusInput {
  lifecycle: CaseLifecycle
  archiveTask?: ArchiveTaskCardSummary | null
  sourceStatus: SourceAccessStatus
  saveState: 'idle' | 'saving' | 'saved' | 'failed' | 'conflict' | 'not_changed'
  saveHasPending: boolean
  photoState: 'ready' | 'uploading' | 'error' | 'warning'
}

const ARCHIVE_STAGE_LABELS: Record<string, string> = {
  queued: '归档任务正在等待处理',
  inventory: '正在整理待归档内容',
  preflight_verified: '归档前检查已完成',
  winrar: '正在生成压缩分卷',
  integrity: '正在校验压缩文件',
  integrity_verified: '压缩文件完整性已确认',
  hash: '正在生成文件校验值',
  manifest: '正在整理归档清单',
  completed: '归档产物已生成，正在确认结果',
}

function formatBytes(bytes: number | null): string | null {
  if (!bytes || bytes < 1) return null
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB 已生成`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB 已生成`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB 已生成`
}

function backgroundArchiveDetail(task: ArchiveTaskCardSummary): string {
  const facts = [
    formatBytes(task.output_bytes),
    task.output_volume_count ? `已检测到 ${task.output_volume_count} 个分卷` : null,
  ].filter(Boolean)
  const stage = ARCHIVE_STAGE_LABELS[task.stage] || '后台任务正在推进'
  return `${stage}；${facts.length ? facts.join('，') : '后台任务正在推进'}。可继续处理其他待办。`
}

export function buildGuidedReviewSystemStatus(
  input: GuidedReviewSystemStatusInput,
): GuidedReviewSystemStatus | null {
  if (input.saveHasPending && input.saveState === 'saving') return {
    title: '正在保存当前输入', detail: '保存完成前，当前输入会继续保留在本页面。',
  }
  if (input.photoState === 'uploading') return { title: '正在保存图片', detail: '图片上传和绑定完成后会自动沿用。' }
  if (input.sourceStatus === 'pending') return { title: '正在复核报告来源', detail: '系统完成快速复核后会更新可办理事项。' }
  if (input.archiveTask && ['archive_queued', 'archiving'].includes(input.lifecycle)) return {
    title: '后台归档处理中',
    detail: backgroundArchiveDetail(input.archiveTask),
  }
  if (input.lifecycle === 'exported') return {
    title: '已完成导出', detail: '案件材料已完成导出，可返回案件工作台继续办理。',
  }
  return null
}
