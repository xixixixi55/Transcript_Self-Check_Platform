import React from 'react'
import {
  CheckCircleOutlined,
  DownloadOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import type { ReviewPageStatus } from './reviewWorkspaceTypes'

interface ReviewSaveStatusProps {
  status: ReviewPageStatus
}

export function ReviewSaveStatus({ status }: ReviewSaveStatusProps) {
  const icon = status === '当前页面修改已更新'
    ? <CheckCircleOutlined />
    : status === '存在未导出修改'
      ? <EditOutlined />
      : ['归档规划中', '归档执行中', '归档校验中', '归档哈希中', '导出中'].includes(status)
        ? <LoadingOutlined />
        : status === '导出成功'
          ? <CheckCircleOutlined />
          : status === '导出失败'
            ? <ExclamationCircleOutlined />
            : <InfoCircleOutlined />

  const detail = status === '当前页面修改已更新'
    ? '仅更新当前页面状态，未写入服务器'
    : status === '存在未导出修改'
      ? '请导出 Word 以生成文件'
      : ['归档规划中', '归档执行中', '归档校验中', '归档哈希中'].includes(status)
        ? '正在生成并校验归档分卷'
        : status === '导出中'
          ? '归档已完成，正在生成 Word'
        : status === '导出成功'
          ? '文件已生成并触发下载'
          : status === '导出失败'
            ? '请根据错误信息修正后重试'
            : '尚未触发页面修改'

  return (
    <div className={`review-save-status review-save-status--${status}`} aria-live="polite" data-status={status}>
      <span className="review-save-status__icon" aria-hidden="true">{icon}</span>
      <span>
        <span className="review-save-status__label">{status}</span>
        <span className="review-save-status__detail">{detail}</span>
      </span>
    </div>
  )
}
