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
      : status === '导出中'
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
      : status === '导出中'
        ? '正在调用现有 Word 导出服务'
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
