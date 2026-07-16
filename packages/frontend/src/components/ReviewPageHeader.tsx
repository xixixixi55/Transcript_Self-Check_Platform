import React from 'react'
import { Button } from 'antd'
import { EyeOutlined } from '@ant-design/icons'
import type { InspectionReport } from '@biji/shared/types'
import { ReviewSaveStatus } from './ReviewSaveStatus'
import type { ReviewPageStatus } from './reviewWorkspaceTypes'

interface ReviewPageHeaderProps {
  report: InspectionReport
  status: ReviewPageStatus
  onPreview: () => void
}

export function ReviewPageHeader({ report, status, onPreview }: ReviewPageHeaderProps) {
  const caseSummary = report.introduction?.case_summary?.trim() || '未识别案件摘要'
  const caseNumber = report.case_number?.trim() || '未识别案件编号'

  return (
    <header className="review-page-header">
      <div className="review-page-header__main">
        <div className="review-breadcrumb">笔录生成 / 审核编辑</div>
        <h1>{report.title || '电子数据检查笔录自动生成'}</h1>
        <div className="review-case-summary" aria-label="案件摘要">
          <span><strong>案件名称/摘要</strong>{caseSummary}</span>
          <span><strong>案件编号</strong>{caseNumber}</span>
        </div>
      </div>
      <div className="review-page-header__actions">
        <ReviewSaveStatus status={status} />
        <Button icon={<EyeOutlined />} onClick={onPreview}>打开结构摘要预览</Button>
      </div>
    </header>
  )
}
