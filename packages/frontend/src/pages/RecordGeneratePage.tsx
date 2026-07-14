// Layer 12: FE_Pages — 笔录生成主页面
// REQ-007/017/018/019: click-to-edit 全字段审核编辑
import React, { useState, useEffect } from 'react'
import { Layout, Steps, Spin } from 'antd'
import type { InspectionReport } from '@biji/shared/types'
import type { UploadFile } from 'antd'
import { useReportParser } from '../hooks/useReportParser'
import { useRecordExport } from '../hooks/useRecordExport'
import { generateDocumentNumber } from '@biji/shared/utils'
import ReportUploadStep from '../components/ReportUploadStep'
import RecordEditorForm from '../components/RecordEditorForm'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'

type UploadMode = 'folder' | 'archive'

export default function RecordGeneratePage() {
  const { parseReport, parseArchive, loading: parsing, result } = useReportParser()
  const { exportDocx, exporting } = useRecordExport()
  const [devices, setDevices] = useState<{ id: string; name: string; model: string }[]>([])
  const [uploadMode, setUploadMode] = useState<UploadMode>('folder')
  const [compress, setCompress] = useState(true)
  const [report, setReport] = useState<InspectionReport | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [photoFiles, setPhotoFiles] = useState<UploadFile[]>([])

  useEffect(() => {
    axios.get(API_ENDPOINTS.DEVICES).then(r => setDevices(r.data.data || []))
  }, [])

  useEffect(() => {
    if (result?.report) {
      const r = JSON.parse(JSON.stringify(result.report))
      const caseNum = (r as any).case_number || ''
      const unit = r.introduction?.entrust_unit || ''
      const prefix = unit.includes('测试地区') ? '测试公' : 'xx'
      r.document_number = generateDocumentNumber(caseNum || '000000', undefined, prefix)
      setReport(r)
      setCurrentStep(1)
    }
  }, [result])

  const handleFolderUpload = async () => {
    const dirPath = prompt('请输入报告目录路径:')
    if (dirPath) await parseReport(dirPath, compress)
  }

  const handleExport = () => {
    if (report) {
      const files = photoFiles.filter(f => f.originFileObj).map(f => f.originFileObj as File)
      exportDocx(report, report.attachments?.photo_ids || [], files.length > 0 ? files : undefined)
    }
  }

  const updateReport = (path: string, value: any) => {
    if (!report) return
    const keys = path.split('.')
    const newReport = JSON.parse(JSON.stringify(report))
    let obj: any = newReport
    for (let i = 0; i < keys.length - 1; i++) obj = obj[keys[i]]
    obj[keys[keys.length - 1]] = value
    setReport(newReport)
  }

  // ─── Step 0: 上传 ───
  if (currentStep === 0) {
    return (
      <ReportUploadStep uploadMode={uploadMode} onModeChange={setUploadMode}
        compress={compress} onCompressChange={setCompress} parsing={parsing} result={result}
        onFolderUpload={handleFolderUpload}
        onArchiveUpload={async (file) => { await parseArchive(file); return false }} />
    )
  }

  if (!report) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  // ─── Step 1: 审核编辑 ───
  return (
    <Layout.Content style={{ padding: 24, maxWidth: 960, margin: '0 auto' }}>
      <Steps current={1} style={{ marginBottom: 16 }}>
        <Steps.Step title="上传报告" /><Steps.Step title="审核编辑" /><Steps.Step title="导出Word" />
      </Steps>
      <RecordEditorForm
        report={report}
        updateReport={updateReport}
        onExport={handleExport}
        exporting={exporting}
        onBackToUpload={() => setCurrentStep(0)}
        deviceOptions={devices.map(d => ({ label: d.name + ' (' + d.model + ')', value: d.name }))}
        photoFiles={photoFiles}
        onPhotoFilesChange={setPhotoFiles}
      />
    </Layout.Content>
  )
}
