import React from 'react'
import { Button, Space } from 'antd'
import { DownloadOutlined, SaveOutlined } from '@ant-design/icons'
import type { ReviewPageStatus } from './reviewWorkspaceTypes'
import { ReviewSaveStatus } from './ReviewSaveStatus'

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
        <Button onClick={onBack} disabled={exporting}>{backLabel}</Button>
        <Button icon={<SaveOutlined />} onClick={onSave} loading={saveBusy} disabled={exporting}>
          保存当前修改
        </Button>
        <Button type="primary" icon={<DownloadOutlined />} onClick={onExport} loading={exporting}>
          导出 Word
        </Button>
      </Space>
    </div>
  )
}
