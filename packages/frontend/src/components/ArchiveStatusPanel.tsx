// Layer 11: FE_Components — compact, safe archive-task summary for a case card.
import React, { useEffect, useState } from 'react'
import type { ArchiveTaskCardSummary } from '@biji/shared/types'

interface Props {
  summary?: ArchiveTaskCardSummary
}

function formatBytes(value: number | null): string | null {
  if (value === null) return null
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let amount = value
  let unit = 0
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024
    unit += 1
  }
  const digits = unit === 0 || amount >= 100 ? 0 : 1
  return `${amount.toFixed(digits)} ${units[unit]}`
}

function formatElapsed(startedAt: string | null, now: number): string | null {
  if (!startedAt) return null
  const elapsed = Math.max(0, now - new Date(startedAt).getTime())
  if (!Number.isFinite(elapsed)) return null
  const minutes = Math.floor(elapsed / 60_000)
  if (minutes < 60) return `已运行 ${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  const remaining = minutes % 60
  return `已运行 ${hours} 小时${remaining ? ` ${remaining} 分钟` : ''}`
}

function formatRelative(value: string | null, now: number): string | null {
  if (!value) return null
  const elapsed = Math.max(0, now - new Date(value).getTime())
  if (!Number.isFinite(elapsed)) return null
  const minutes = Math.floor(elapsed / 60_000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  return hours < 24 ? `${hours} 小时前` : `${Math.floor(hours / 24)} 天前`
}

function formatDate(value: string | null): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '时间未知'
    : date.toLocaleString('zh-CN', { hour12: false })
}

function resolveState(summary: ArchiveTaskCardSummary): string {
  if (summary.status === 'succeeded') return '归档完成'
  if (summary.status === 'cancelled') return '已取消'
  if (summary.status === 'failed_retryable' || summary.status === 'failed_terminal') return '归档失败'
  if (summary.worker_state === 'recovering') return '恢复中'
  if (summary.worker_state === 'waiting_reclaim' || summary.status === 'interrupted') return '等待接管'
  if (summary.status === 'queued' || summary.status === 'blocked') return '等待归档'
  if (summary.status === 'cancelling') return '正在取消'
  return '归档中'
}

function activityLines(summary: ArchiveTaskCardSummary, now: number): string[] {
  if (summary.status === 'succeeded') {
    const volumes = summary.output_volume_count === null ? null : `${summary.output_volume_count} 个分卷`
    return [`总体里程碑 100%${volumes ? ` · ${volumes}` : ''}`, `完成时间：${formatDate(summary.finished_at)}`]
  }
  if (summary.status === 'cancelled') {
    return [`取消时阶段：${summary.stage_label}`, `取消时间：${formatDate(summary.finished_at)}`]
  }
  if (summary.status === 'failed_retryable' || summary.status === 'failed_terminal') {
    return [`失败阶段：${summary.stage_label}`, summary.error_summary || '失败原因可在任务详情中查看']
  }
  const state = resolveState(summary)
  if (state === '恢复中' || state === '等待接管' || state === '等待归档') {
    return [`总体里程碑 ${summary.percent}% · 保留最后确认状态`, '任务当前未在运行']
  }

  const elapsed = formatElapsed(summary.started_at, now)
  const first = `总体里程碑 ${summary.percent}%${elapsed ? ` · ${elapsed}` : ''}`
  const metrics = [
    summary.output_volume_count === null ? null : `已检测 ${summary.output_volume_count} 个分卷`,
    formatBytes(summary.output_bytes) ? `已写出约 ${formatBytes(summary.output_bytes)}` : null,
  ].filter(Boolean).join(' · ')
  const lastActivity = formatRelative(
    summary.last_output_change_at ?? summary.last_heartbeat_at,
    now,
  )
  const second = [metrics || null, lastActivity ? `最后活动：${lastActivity}` : null]
    .filter(Boolean)
    .join(' · ')
  return second ? [first, second] : [first]
}

export function ArchiveStatusPanel({ summary }: Props) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!summary || summary.status !== 'running') return undefined
    const timer = window.setInterval(() => setNow(Date.now()), 60_000)
    return () => window.clearInterval(timer)
  }, [summary?.task_id, summary?.status])

  if (!summary) {
    return (
      <section className="archive-status-panel" aria-label="归档状态：未归档">
        <div className="archive-status-panel__heading"><strong>未归档</strong></div>
        <div className="archive-status-panel__stage">可进行归档前检查或开始归档</div>
      </section>
    )
  }

  const state = resolveState(summary)
  const isActiveWinRar = summary.status === 'running'
    && summary.stage === 'winrar'
    && summary.worker_state === 'owned_running'
  return (
    <section
      className={`archive-status-panel archive-status-panel--${summary.status}`}
      aria-label={`归档状态：${state}；当前阶段：${summary.stage_label}`}
      role="status"
    >
      <div className="archive-status-panel__heading">
        <strong>{state}</strong>
        <span>阶段 {summary.stage_index} / {summary.stage_count}</span>
      </div>
      <div className="archive-status-panel__stage">{summary.stage_label}</div>
      {isActiveWinRar && (
        <div
          className="archive-status-panel__indeterminate"
          role="progressbar"
          aria-label="任务正在运行：正在创建 RAR 分卷"
        ><span /></div>
      )}
      <div className="archive-status-panel__activity">
        {activityLines(summary, now).map((line, index) => (
          <div
            className={index === 1 ? 'archive-status-panel__activity-line archive-status-panel__activity-line--secondary' : 'archive-status-panel__activity-line'}
            key={line}
            title={line}
          >{line}</div>
        ))}
      </div>
    </section>
  )
}
