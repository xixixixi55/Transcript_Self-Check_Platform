// Layer 12: FE_Pages - 笔录生成主页面
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Spin, Steps, type UploadFile } from 'antd'
import type { InspectorLibraryRecord, InspectionReport } from '@biji/shared/types'
import { useReportParser } from '../hooks/useReportParser'
import { useRecordExport } from '../hooks/useRecordExport'
import { usePreviewArchive } from '../hooks/useArchivePreparation'
import { useReportDefaults } from '../hooks/useReportDefaults'
import { getReviewPendingItems } from '../hooks/useReviewChecklist'
import { useReviewWorkspaceShortcuts } from '../hooks/useReviewWorkspaceShortcuts'
import {
  applyReportEdit, generateDocumentNumber, getDefaultExportFileName, isValidDateFieldValue,
  isValidMinuteTimeRangeValue, normalizeDataSummary, validateExportFileName,
} from '@biji/shared/utils'
import ReportUploadStep from '../components/ReportUploadStep'
import RecordEditorForm from '../components/RecordEditorForm'
import { ReviewPageHeader } from '../components/ReviewPageHeader'
import { ReviewPendingSummary } from '../components/ReviewPendingSummary'
import { ReviewPreviewDrawer } from '../components/ReviewPreviewDrawer'
import type { ReviewPageStatus } from '../components/reviewWorkspaceTypes'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
type UploadMode = 'folder' | 'archive'
export default function RecordGeneratePage() {
  const { parseReport, parseArchive, loading: parsing, error, errorCode, result, clearReportParsingCache, clearingCache, cacheClearMessage, cacheClearError } = useReportParser()
  const { exportDocx, exporting } = useRecordExport()
  const reportDefaults = useReportDefaults()
  const [devices, setDevices] = useState<{ id: string; name: string; model: string }[]>([])
  const [inspectors, setInspectors] = useState<InspectorLibraryRecord[]>([])
  const [inspectorLoading, setInspectorLoading] = useState(false)
  const [inspectorError, setInspectorError] = useState<string | null>(null)
  const [uploadMode, setUploadMode] = useState<UploadMode>('folder')
  const [report, setReport] = useState<InspectionReport | null>(null)
  const [archiveContextId, setArchiveContextId] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [photoFiles, setPhotoFiles] = useState<UploadFile[]>([])
  const [customFileName, setCustomFileName] = useState(false)
  const [exportFileName, setExportFileName] = useState('')
  const [exportFileNameError, setExportFileNameError] = useState('')
  const [reviewStatus, setReviewStatus] = useState<ReviewPageStatus>('尚未修改')
  const [hasPageChanges, setHasPageChanges] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const archive = usePreviewArchive(report, setReport, archiveContextId)
  useEffect(() => {
    axios.get(API_ENDPOINTS.DEVICES).then(r => setDevices(r.data.data || []))
  }, [])
  useEffect(() => {
    setInspectorLoading(true)
    axios.get(API_ENDPOINTS.INSPECTORS, { params: { enabled_only: true } })
      .then(r => {
        setInspectors(r.data.data || [])
        setInspectorError(null)
      })
      .catch(() => setInspectorError('获取启用检查人员失败，请稍后重试。'))
      .finally(() => setInspectorLoading(false))
  }, [])
  useEffect(() => {
    if (result?.report) {
      let r = JSON.parse(JSON.stringify(result.report))
      r.inspection = r.inspection || {}
      r.inspection.result = r.inspection.result || {}
      r.inspection.result.data_summary = normalizeDataSummary(r.inspection.result.data_summary)
      const caseNum = (r as any).case_number || ''
      const unit = r.introduction?.entrust_unit || ''
      const prefix = unit.includes('测试地区') ? '测试公' : 'xx'
      // 后端返回有默认文号则保留，只有空或占位符才自动生成
      if (!r.document_number || r.document_number.startsWith('xx电检')) {
        r.document_number = generateDocumentNumber(caseNum || '000000', undefined, prefix)
      }
      r = reportDefaults.applyDefaults(r)
      setReport(r)
      setArchiveContextId(result.archive_context_id || null)
      archive.reset()
      setExportFileName(getDefaultExportFileName(r.document_number))
      setCustomFileName(false)
      setExportFileNameError('')
      setReviewStatus('尚未修改')
      setHasPageChanges(false)
      setPreviewOpen(false)
      setCurrentStep(1)
    }
  }, [result, archive.reset, reportDefaults.applyDefaults])
  const handleFolderUpload = async () => {
    const dirPath = prompt('请输入报告目录路径:')
    if (dirPath) await parseReport(dirPath)
  }
  const handleExport = async () => {
    if (!report || exporting) return false
    const dateErrors = [
      !isValidDateFieldValue(report.introduction.entrust_time) && '委托时间',
      !isValidMinuteTimeRangeValue(report.introduction.inspection_time_range) && '检查起止时间',
      report.attachments?.burning_date && !isValidDateFieldValue(report.attachments.burning_date) && '附件3刻录时间',
    ].filter(Boolean)
    if (dateErrors.length > 0) {
      setReviewStatus('导出失败')
      alert(`请修正以下日期时间字段后再导出：${dateErrors.join('、')}`)
      return false
    }

    const requestedFileName = customFileName ? exportFileName : getDefaultExportFileName(report.document_number)
    if (customFileName) {
      const error = validateExportFileName(exportFileName)
      if (error) {
        setExportFileNameError(error)
        setReviewStatus('导出失败')
        alert(error)
        return false
      }
    }

    const files = photoFiles.filter(file => file.originFileObj).map(file => file.originFileObj as File)
    const photoIds = files.map(file => file.name)
    setReviewStatus('导出中')
    const success = await exportDocx(
      report,
      photoIds,
      files.length > 0 ? files : undefined,
      requestedFileName,
      archive.manifest ? archiveContextId : null,
      archive.manifest?.manifest_id ?? null,
    )
    setReviewStatus(success ? '导出成功' : '导出失败')
    return success
  }
  const handleCustomFileNameChange = (enabled: boolean) => {
    setCustomFileName(enabled)
    setExportFileNameError('')
    if (!enabled && report) setExportFileName(getDefaultExportFileName(report.document_number))
  }
  const handleExportFileNameChange = (value: string) => {
    setExportFileName(value)
    setExportFileNameError('')
  }

  useEffect(() => {
    if (report && !customFileName) setExportFileName(getDefaultExportFileName(report.document_number))
  }, [report?.document_number, customFileName])
  const updateReport = (path: string, value: any) => {
    if (!report) return
    archive.reset()
    const newReport = applyReportEdit(report, path, value)
    setReport(newReport)
    setHasPageChanges(true)
    setReviewStatus('存在未导出修改')
  }
  const handleSave = useCallback(() => {
    if (saveBusy) return
    setSaveBusy(true)
    setReviewStatus('当前页面修改已更新')
    window.setTimeout(() => setSaveBusy(false), 350)
  }, [saveBusy])

  const handleBackToUpload = () => {
    if (hasPageChanges && !window.confirm('当前页面存在未导出修改，确定返回重新上传吗？')) return
    setPreviewOpen(false)
    setReviewStatus('尚未修改')
    setHasPageChanges(false)
    setCurrentStep(0)
  }
  const pendingItems = useMemo(() => {
    return report ? getReviewPendingItems(report, customFileName ? exportFileNameError : undefined) : []
  }, [customFileName, exportFileNameError, report])

  const navigateToSection = (sectionId: string) => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  useReviewWorkspaceShortcuts({
    onSave: handleSave,
    previewOpen,
    onClosePreview: () => setPreviewOpen(false),
    enabled: Boolean(report && currentStep === 1),
  })

  if (currentStep === 0) {
    return (
      <div className="platform-flow-page">
        <ReportUploadStep
          uploadMode={uploadMode}
          onModeChange={setUploadMode}
          parsing={parsing}
          result={result}
          error={error}
          errorCode={errorCode}
          onFolderUpload={handleFolderUpload}
          onArchiveUpload={async file => { await parseArchive(file); return false }}
          onClearReportCache={clearReportParsingCache} clearingCache={clearingCache}
          cacheClearMessage={cacheClearMessage} cacheClearError={cacheClearError}
        />
      </div>
    )
  }
  if (!report) return <div className="platform-flow-page"><Spin size="large" style={{ display: 'block', margin: '100px auto' }} /></div>

  return (
    <>
      <div className="review-page">
        <ReviewPageHeader report={report} status={reviewStatus} onPreview={() => setPreviewOpen(true)} />
        <div className="review-steps" aria-label="当前步骤">
          <Steps current={1}>
            <Steps.Step title="上传报告" />
            <Steps.Step title="审核编辑" />
            <Steps.Step title="导出 Word" />
          </Steps>
        </div>
        <ReviewPendingSummary items={pendingItems} onNavigate={navigateToSection} />
        <RecordEditorForm
          report={report}
          updateReport={updateReport}
          onExport={handleExport}
          exporting={exporting || reviewStatus === '导出中'}
          onBackToUpload={handleBackToUpload}
          deviceOptions={devices.map(device => ({ label: `${device.name} (${device.model})`, value: device.name }))}
          availableInspectors={inspectors}
          inspectorLoading={inspectorLoading}
          inspectorError={inspectorError}
          photoFiles={photoFiles}
          onPhotoFilesChange={files => { archive.reset(); setPhotoFiles(files) }}
          exportFileName={exportFileName}
          customFileName={customFileName}
          exportFileNameError={exportFileNameError}
          onCustomFileNameChange={handleCustomFileNameChange}
          onExportFileNameChange={handleExportFileNameChange}
          hasReportDefaults={reportDefaults.hasDefaults}
          defaultDiscPrefix={reportDefaults.defaults.disc_number_prefix}
          onSaveReportDefaults={() => reportDefaults.saveCurrentReport(report)}
          onClearReportDefaults={reportDefaults.clearDefaults} onDefaultDiscPrefixChange={reportDefaults.saveDiscPrefix}
          saveStatus={reviewStatus}
          saveBusy={saveBusy}
          onSave={handleSave}
          pendingItems={pendingItems}
          archiveContextId={archiveContextId}
          archiveStatus={archive.status}
          archivePreparing={archive.loading}
          onPrepareArchive={() => { if (report && archiveContextId) void archive.prepare(report, archiveContextId) }}
          archiveManifest={archive.manifest}
          archiveError={archive.error}
        />
      </div>
      <ReviewPreviewDrawer open={previewOpen} report={report} onClose={() => setPreviewOpen(false)} />
    </>
  )
}
