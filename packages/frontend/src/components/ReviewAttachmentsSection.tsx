import React from 'react'
import { Alert, Typography } from 'antd'
import type { UploadFile } from 'antd'
import type { ArchiveMedium, EvidenceItem, InspectionReport } from '@biji/shared/types'
import { formatDiscDate, parseDiscSequence } from '@biji/shared/utils'
import ExtractListEditor from './ExtractListEditor'
import ImageUploader from './ImageUploader'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

const { Text } = Typography

interface ReviewAttachmentsSectionProps {
  attachments: InspectionReport['attachments']
  materials: EvidenceItem[]
  hardwareDevice: string
  photoFiles: UploadFile[]
  onPhotoFilesChange: (files: UploadFile[]) => void
  updateReport: (path: string, value: any) => void
  archiveMedium?: ArchiveMedium | null
}

export function ReviewAttachmentsSection({ attachments, materials, hardwareDevice, photoFiles, onPhotoFilesChange, updateReport, archiveMedium = 'optical_disc' }: ReviewAttachmentsSectionProps) {
  const discResult = parseDiscSequence(attachments.disc_number || '')
  const expectedPrefixes = archiveMedium === 'hard_drive' ? ['YP'] : archiveMedium === 'optical_disc' ? ['GP'] : ['GP', 'YP']
  const mediumNumberValid = discResult.valid && expectedPrefixes.includes(discResult.sequence?.prefix || '')
  const hardDrive = archiveMedium === 'hard_drive'
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
        <ImageUploader materials={materials} photos={photoFiles} onChange={onPhotoFilesChange} />
      </div>
      {mediumNumberValid && discResult.sequence ? (
        <div id={REVIEW_TARGET_IDS.burningDate} className="review-field review-navigation-target" tabIndex={-1}>
          <div className="review-field__label">附件摘要/附件3日期</div>
          <Text>{formatDiscDate(discResult.sequence.date)}</Text>
          <Text type="secondary">{hardDrive
            ? '该硬盘编号对应唯一完整 RAR。'
            : archiveMedium === 'optical_disc'
              ? '后续光盘编号将在最终卷数确定后按序号自动生成。'
              : '压缩完成后，系统将按最终介质类型确认该编号。'}</Text>
        </div>
      ) : attachments.disc_number ? (
        <div id={REVIEW_TARGET_IDS.burningDate} className="review-navigation-target" tabIndex={-1}>
          <Alert type="error" showIcon message={hardDrive
            ? '硬盘编号必须符合 YPyyyyMMdd-序号 格式且日期真实有效，导出前必须修正。'
            : archiveMedium === 'optical_disc'
              ? '首个光盘编号必须符合 GPyyyyMMdd-序号 格式且日期真实有效，导出前必须修正。'
              : '介质编号必须符合 GPyyyyMMdd-序号 或 YPyyyyMMdd-序号 格式且日期真实有效。'} />
        </div>
      ) : null}
    </>
  )
}
