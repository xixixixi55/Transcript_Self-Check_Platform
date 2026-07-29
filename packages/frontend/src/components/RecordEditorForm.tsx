// Layer 11: FE_Components - 笔录审核编辑表单
import React from 'react'
import { Alert, Button, Space, Typography } from 'antd'
import type {
  ArchiveLifecycleStatus,
  ArchiveManifest,
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
  fieldStates?: Record<string, FieldState>
  defaultDiscPrefix?: string
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
  workbenchMode?: boolean
  readOnly?: boolean
  draftSaveStatus?: string
  sharedDefaultsSaveStatus?: string
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
  defaultDiscPrefix = '',
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
  workbenchMode = false,
  readOnly = false,
  draftSaveStatus = '',
  sharedDefaultsSaveStatus = '',
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
          <ReviewField label="文号" type="text" value={report.document_number}
            onChange={value => updateReport('document_number', value)} />
          {workbenchMode && <div className="review-export-settings">
            <div className="review-field__label">共享默认值设置</div>
            <div>保存范围：文号、检查地点、检查方法、检查硬件设备、检查人员、光盘编号前缀</div>
            <div>当前默认光盘编号前缀：{defaultDiscPrefix || '未设置'}</div>
            <div>修改六项字段并成功保存后，只更新本轮明确修改的共享默认值；空值不执行清除。</div>
          </div>}
          {workbenchMode ? <div className="review-export-settings"><div>案件草稿和共享默认值会分别显示保存结果。</div><div>案件草稿：{draftSaveStatus || '尚未保存'}；共享默认值：{sharedDefaultsSaveStatus || '本次未更新'}</div></div> : <div className="review-export-settings">
            <div className="review-field__label">常用字段默认设置</div>
            <div>保存范围：文号、检查地点、检查方法、检查硬件设备、检查人员、光盘编号前缀</div>
            <div>当前默认光盘编号前缀：{defaultDiscPrefix || '未设置'}</div>
            <div>修改六项字段并成功保存后，只更新本轮明确修改的共享默认值；空值不执行清除。</div>
          </div>}
        <Alert message="请谨慎修改文号；每次导出均会询问本次 Word 下载文件名。" type="warning" showIcon />
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
