// Layer 11: FE_Components - 笔录审核编辑表单
import React from 'react'
import { Alert, Button, Checkbox, Input, Space, Typography } from 'antd'
import type {
  ArchiveLifecycleStatus,
  ArchiveManifest,
  InspectorLibraryRecord,
  InspectionReport,
} from '@biji/shared/types'
import type { UploadFile } from 'antd'
import { ReviewActionBar } from './ReviewActionBar'
import { ReviewAttachmentsSection } from './ReviewAttachmentsSection'
import { ReviewField } from './ReviewField'
import { ReviewInspectionSection } from './ReviewInspectionSection'
import { ReviewIntroductionSection } from './ReviewIntroductionSection'
import { ReviewSection } from './ReviewSection'
import type { ReviewPageStatus } from './reviewWorkspaceTypes'
import { REVIEW_SECTION_IDS } from '../hooks/useReviewChecklist'
import type { ReviewPendingItem } from '../hooks/useReviewChecklist'
import EditableField from './EditableField'
import { ArchiveStatusCard } from './ArchiveStatusCard'

const { Title } = Typography

interface Props {
  report: InspectionReport
  updateReport: (path: string, value: any) => void
  onExport: () => void
  exporting: boolean
  onBackToUpload: () => void
  deviceOptions: { label: string; value: string }[]
  availableInspectors?: InspectorLibraryRecord[]
  inspectorLoading?: boolean
  inspectorError?: string | null
  photoFiles: UploadFile[]
  onPhotoFilesChange: (files: UploadFile[]) => void
  exportFileName: string
  customFileName: boolean
  exportFileNameError?: string
  onCustomFileNameChange: (enabled: boolean) => void
  onExportFileNameChange: (value: string) => void
  hasReportDefaults?: boolean
  defaultDiscPrefix?: string
  onSaveReportDefaults?: () => void
  onClearReportDefaults?: () => void
  onDefaultDiscPrefixChange?: (value: string) => void
  saveStatus?: ReviewPageStatus
  saveBusy?: boolean
  onSave?: () => void
  pendingItems?: ReviewPendingItem[]
  archiveContextId?: string | null
  archiveStatus?: ArchiveLifecycleStatus
  archivePreparing?: boolean
  onPrepareArchive?: () => void
  archiveManifest?: ArchiveManifest | null
  archiveError?: string | null
}

export default function RecordEditorForm({
  report,
  updateReport,
  onExport,
  exporting,
  onBackToUpload,
  deviceOptions,
  availableInspectors = [],
  inspectorLoading = false,
  inspectorError = null,
  photoFiles,
  onPhotoFilesChange,
  exportFileName,
  customFileName,
  exportFileNameError,
  onCustomFileNameChange,
  onExportFileNameChange,
  hasReportDefaults = false,
  defaultDiscPrefix = '',
  onSaveReportDefaults = () => undefined,
  onClearReportDefaults = () => undefined,
  onDefaultDiscPrefixChange = () => undefined,
  saveStatus = '尚未修改',
  saveBusy = false,
  onSave = () => undefined,
  pendingItems = [],
  archiveContextId = null,
  archiveStatus = 'not_prepared',
  archivePreparing = false,
  onPrepareArchive = () => undefined,
  archiveManifest = null,
  archiveError = null,
}: Props) {
  const introduction = report.introduction
  const attachments = report.attachments || { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' }
  const countFor = (sectionId: string) => pendingItems.filter(item => item.sectionId === sectionId).length

  return (
    <div className="review-editor-form">
      <div className="review-editor-form__title-row">
        <div>
          <Title level={2}>审核编辑</Title>
          <p>请核对解析内容，点击字段值即可编辑；当前页面不会自动写入服务器。</p>
        </div>
        <span className="review-editor-form__document-number">文号：{report.document_number || '未填写'}</span>
      </div>

      <ReviewSection id={REVIEW_SECTION_IDS.document} title="文书信息与导出设置" pendingCount={countFor(REVIEW_SECTION_IDS.document)}>
        <ReviewField label="文号" type="text" value={report.document_number}
          onChange={value => updateReport('document_number', value)} />
        <div className="review-export-settings">
          <div className="review-field__label">常用字段默认设置</div>
          <div>保存范围：文号、检查地点、检查方法、检查硬件设备、检查人员、光盘编号前缀</div>
          <Input aria-label="默认光盘编号前缀" value={defaultDiscPrefix}
            onChange={event => onDefaultDiscPrefixChange(event.target.value)} placeholder="例如 GP 或 测试公" />
          <Space wrap>
            <Button onClick={onSaveReportDefaults}>保存当前六项为默认值</Button>
            {hasReportDefaults && <><span>已保存默认设置</span><Button onClick={onClearReportDefaults}>清除全部默认值</Button></>}
          </Space>
        </div>
        <Alert message="请谨慎修改文号，导出文件名会使用当前文号生成。" type="warning" showIcon />
        <div className="review-export-settings">
          <div className="review-field__label">导出文件名</div>
          <Checkbox checked={customFileName} onChange={event => onCustomFileNameChange(event.target.checked)}>
            自定义文件名
          </Checkbox>
          <Input
            aria-label="导出文件名"
            value={exportFileName}
            disabled={!customFileName}
            status={exportFileNameError ? 'error' : undefined}
            onChange={event => onExportFileNameChange(event.target.value)}
            placeholder="请输入不含或包含 .docx 的文件名"
          />
          {exportFileNameError && <span className="review-field__error">{exportFileNameError}</span>}
        </div>
      </ReviewSection>

      <ReviewSection id={REVIEW_SECTION_IDS.introduction} title="一、绪论" pendingCount={countFor(REVIEW_SECTION_IDS.introduction)}>
        <ReviewIntroductionSection
          introduction={introduction}
          updateReport={updateReport}
          availableInspectors={availableInspectors}
          inspectorLoading={inspectorLoading}
          inspectorError={inspectorError}
        />
      </ReviewSection>

      <ReviewSection id={REVIEW_SECTION_IDS.inspection} title="二、检查" pendingCount={countFor(REVIEW_SECTION_IDS.inspection)}>
        <ReviewInspectionSection inspection={report.inspection} updateReport={updateReport} deviceOptions={deviceOptions} />
      </ReviewSection>

      <ReviewSection id={REVIEW_SECTION_IDS.attachments} title="附件" pendingCount={countFor(REVIEW_SECTION_IDS.attachments)}>
        <ArchiveStatusCard
          contextId={archiveContextId}
          status={archiveStatus}
          loading={archivePreparing}
          onPrepare={onPrepareArchive}
          manifest={archiveManifest}
          error={archiveError}
        />
        <ReviewAttachmentsSection attachments={attachments} photoFiles={photoFiles}
          onPhotoFilesChange={onPhotoFilesChange} updateReport={updateReport}
          defaultDiscPrefix={defaultDiscPrefix} />
      </ReviewSection>

      <ReviewActionBar
        status={saveStatus}
        saveBusy={saveBusy}
        exporting={exporting}
        onSave={onSave}
        onBack={onBackToUpload}
        onExport={onExport}
      />
    </div>
  )
}
