import React from 'react'
import { Alert, Typography } from 'antd'
import type { UploadFile } from 'antd'
import type { InspectionReport } from '@biji/shared/types'
import { formatDiscDate, parseDiscSequence } from '@biji/shared/utils'
import ExtractListEditor from './ExtractListEditor'
import ImageUploader from './ImageUploader'

const { Text } = Typography

interface ReviewAttachmentsSectionProps {
  attachments: InspectionReport['attachments']
  hardwareDevice: string
  photoFiles: UploadFile[]
  onPhotoFilesChange: (files: UploadFile[]) => void
  updateReport: (path: string, value: any) => void
}

export function ReviewAttachmentsSection({ attachments, hardwareDevice, photoFiles, onPhotoFilesChange, updateReport }: ReviewAttachmentsSectionProps) {
  const discResult = parseDiscSequence(attachments.disc_number || '')
  const extractionMethod = `使用${hardwareDevice.trim() || '取证设备'}对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值`

  return (
    <>
      <div className="review-editor-block">
        <div className="review-field__label">附件1：电子数据提取固定清单</div>
        <ExtractListEditor tableData={attachments.extract_list || { columns: [], rows: [] }}
          fallbackExtractionMethod={extractionMethod}
          onChange={value => updateReport('attachments.extract_list', value)} />
      </div>
      <div className="review-editor-block">
        <div className="review-field__label">附件2：检材照片</div>
        <ImageUploader photos={photoFiles} onChange={onPhotoFilesChange} />
      </div>
      {discResult.valid && discResult.sequence ? (
        <div className="review-field">
          <div className="review-field__label">附件摘要/附件3日期</div>
          <Text>{formatDiscDate(discResult.sequence.date)}</Text>
          <Text type="secondary">后续光盘编号将在最终卷数确定后按序号自动生成。</Text>
        </div>
      ) : attachments.disc_number ? (
        <Alert type="error" showIcon message="首个光盘编号格式或日期无效，导出前必须修正。" />
      ) : null}
    </>
  )
}
