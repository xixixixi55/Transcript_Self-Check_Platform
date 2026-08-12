// Layer 11: FE_Components - 笔录审核编辑表单
import React from 'react'
import { Button, Space, Typography } from 'antd'
import type {
  ArchiveLifecycleStatus,
  ArchiveManifest,
  ArchiveTaskResult,
  InspectorLibraryRecord,
  InspectionReport,
  FieldState,
} from '@biji/shared/types'
import type { UploadFile } from 'antd'
import { ReviewActionBar } from './ReviewActionBar'
import { ReviewAttachmentsSection } from './ReviewAttachmentsSection'
import { ReviewField } from './ReviewField'
import { ReviewInspectionSection } from './ReviewInspectionSection'
import { ReviewIntroductionSection } from './ReviewIntroductionSection'
import { ReviewSection } from './ReviewSection'
import type { ReviewPageStatus } from './reviewWorkspaceTypes'
import { REVIEW_SECTION_IDS, REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'
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
  fieldStates?: Record<string, FieldState>
  /** Deprecated UI compatibility props; defaults are updated by successful draft saves. */
  hasReportDefaults?: boolean
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
  archiveResult?: { result: ArchiveTaskResult | null; loading: boolean; error: string | null }
  workbenchMode?: boolean
  readOnly?: boolean
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
  fieldStates,
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
  archiveResult = { result: null, loading: false, error: null },
  workbenchMode = false,
  readOnly = false,
}: Props) {
  const introduction = report.introduction
  const attachments = report.attachments || { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' }
  const countFor = (sectionId: string) => pendingItems.filter(item => item.sectionId === sectionId).length

  return (
    <div className="review-editor-form">
      <div className="review-editor-form__title-row">
        <div>
          <Title level={2}>审核编辑</Title>
          <p>{workbenchMode ? '请核对解析内容；修改会按 revision 自动保存到案件草稿。' : '请核对解析内容，点击字段值即可编辑；当前页面不会自动写入服务器。'}</p>
        </div>
        <span className="review-editor-form__document-number">文号：{report.document_number || '未填写'}</span>
      </div>

      <fieldset disabled={readOnly} className="review-editor-form__fieldset">
        <ReviewSection id={REVIEW_SECTION_IDS.document} title="文书信息与导出设置" pendingCount={countFor(REVIEW_SECTION_IDS.document)}>
          <ReviewField targetId={REVIEW_TARGET_IDS.documentNumber} label="文号" type="text" value={report.document_number}
            onChange={value => updateReport('document_number', value)} />
        </ReviewSection>

        <ReviewSection id={REVIEW_SECTION_IDS.introduction} title="一、绪论" pendingCount={countFor(REVIEW_SECTION_IDS.introduction)}>
        <ReviewIntroductionSection
          introduction={introduction}
          updateReport={updateReport}
          availableInspectors={availableInspectors}
          inspectorLoading={inspectorLoading}
          inspectorError={inspectorError}
          fieldStates={fieldStates}
        />
        </ReviewSection>

        <ReviewSection id={REVIEW_SECTION_IDS.inspection} title="二、检查" pendingCount={countFor(REVIEW_SECTION_IDS.inspection)}>
        <ReviewInspectionSection inspection={report.inspection} updateReport={updateReport} deviceOptions={deviceOptions} />
        </ReviewSection>

        <ReviewSection id={REVIEW_SECTION_IDS.attachments} title="附件" pendingCount={countFor(REVIEW_SECTION_IDS.attachments)}>
        {(!workbenchMode || archiveResult.result || archiveResult.error) && <ArchiveStatusCard
            contextId={archiveContextId}
            status={archiveResult.result ? 'completed' : archiveResult.error ? 'failed' : archiveStatus}
            loading={archivePreparing}
            onPrepare={onPrepareArchive}
            manifest={archiveManifest}
            resultParts={archiveResult.result?.parts}
            taskId={archiveResult.result?.task_id}
            error={archiveError || archiveResult.error}
          />}
        <ReviewAttachmentsSection attachments={attachments} hardwareDevice={report.inspection?.hardware_device || ''} photoFiles={photoFiles}
          onPhotoFilesChange={onPhotoFilesChange} updateReport={updateReport} />
        </ReviewSection>
      </fieldset>

      <ReviewActionBar
        status={saveStatus}
        saveBusy={saveBusy}
        exporting={exporting}
        backLabel={workbenchMode ? '返回案件工作台' : undefined}
        onSave={onSave}
        onBack={onBackToUpload}
        onExport={onExport}
      />
    </div>
  )
}
