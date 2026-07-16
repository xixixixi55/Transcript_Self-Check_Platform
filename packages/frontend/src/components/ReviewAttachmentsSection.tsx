import React from 'react'
import type { UploadFile } from 'antd'
import type { InspectionReport } from '@biji/shared/types'
import ExtractListEditor from './ExtractListEditor'
import ImageUploader from './ImageUploader'
import { DateTimeField } from './DateTimeField'
import { ReviewField } from './ReviewField'

interface ReviewAttachmentsSectionProps {
  attachments: InspectionReport['attachments']
  photoFiles: UploadFile[]
  onPhotoFilesChange: (files: UploadFile[]) => void
  updateReport: (path: string, value: any) => void
}

export function ReviewAttachmentsSection({ attachments, photoFiles, onPhotoFilesChange, updateReport }: ReviewAttachmentsSectionProps) {
  return (
    <>
      <div className="review-editor-block">
        <div className="review-field__label">附件1：电子数据提取固定清单</div>
        <ExtractListEditor tableData={attachments.extract_list || { columns: [], rows: [] }}
          onChange={value => updateReport('attachments.extract_list', value)} />
      </div>
      <div className="review-editor-block">
        <div className="review-field__label">附件2：检材照片</div>
        <ImageUploader photos={photoFiles} onChange={onPhotoFilesChange} />
      </div>
      <ReviewField label="附件3：光盘编号" type="text" value={attachments.disc_number}
        onChange={value => updateReport('attachments.disc_number', value)} />
      <DateTimeField label="附件3：刻录时间" precision="date" value={attachments.burning_date || ''}
        onChange={value => updateReport('attachments.burning_date', value)} />
    </>
  )
}
