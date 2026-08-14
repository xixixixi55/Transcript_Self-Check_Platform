import React from 'react'
import { Button, Space, Tooltip } from 'antd'
import { FileWordOutlined, SaveOutlined } from '@ant-design/icons'
import type { ReviewPageStatus } from './reviewWorkspaceTypes'
import { ReviewSaveStatus } from './ReviewSaveStatus'

function RoundedBackIcon() {
  return (
    <svg
      className="review-action-bar__back-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M9 5 4 10l5 5" />
      <path d="M4 10h10a6 6 0 0 1 0 12H8" />
    </svg>
  )
}

interface ReviewActionBarProps {
  status: ReviewPageStatus
  saveBusy: boolean
  exporting: boolean
  backLabel?: string
  onSave: () => void
  onBack: () => void
  onExport: () => void
}

export function ReviewActionBar({ status, saveBusy, exporting, backLabel = '返回重新上传', onSave, onBack, onExport }: ReviewActionBarProps) {
  return (
    <div className="review-action-bar">
      <ReviewSaveStatus status={status} />
      <Space className="review-action-bar__buttons">
        <Tooltip title={backLabel}>
          <Button
            shape="circle"
            size="large"
            aria-label={backLabel}
            icon={<RoundedBackIcon />}
            onClick={onBack}
            disabled={exporting}
          />
        </Tooltip>
        <Tooltip title="保存当前修改">
          <Button
            shape="circle"
            size="large"
            aria-label="保存当前修改"
            icon={<SaveOutlined />}
            onClick={onSave}
            loading={saveBusy}
            disabled={exporting}
          />
        </Tooltip>
        <Tooltip title="导出 Word">
          <Button
            type="primary"
            shape="circle"
            size="large"
            aria-label="导出 Word"
            icon={<FileWordOutlined />}
            onClick={onExport}
            loading={exporting}
          />
        </Tooltip>
      </Space>
    </div>
  )
}
