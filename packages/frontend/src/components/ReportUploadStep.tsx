// Layer 11: FE_Components — 报告上传步骤
// 提取自 RecordGeneratePage 以控制文件大小
import React from 'react'
import { Button, Card, Checkbox, Radio, Steps, Typography, Alert, Upload, message } from 'antd'
import { UploadOutlined, InboxOutlined } from '@ant-design/icons'
import FileInfoCard from './FileInfoCard'
import type { ParseReportResponse } from '@biji/shared/types'
import { SUPPORTED_ARCHIVE_FORMATS } from '@biji/shared/constants'

const { Title } = Typography
const { Dragger } = Upload

type UploadMode = 'folder' | 'archive'

interface Props {
  uploadMode: UploadMode
  onModeChange: (mode: UploadMode) => void
  compress: boolean
  onCompressChange: (v: boolean) => void
  parsing: boolean
  result: ParseReportResponse | null
  onFolderUpload: () => void
  onArchiveUpload: (file: File) => Promise<boolean>
}

export default function ReportUploadStep({
  uploadMode, onModeChange, compress, onCompressChange,
  parsing, result, onFolderUpload, onArchiveUpload,
}: Props) {
  const handleArchive = async (file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!SUPPORTED_ARCHIVE_FORMATS.includes(ext)) {
      message.error('仅支持 .rar 和 .zip 格式的压缩包')
      return false
    }
    return onArchiveUpload(file)
  }

  return (
    <div style={{ padding: 48, maxWidth: 800, margin: '0 auto' }}>
      <Card>
        <Title level={3}>电子数据检查笔录 — 自动生成</Title>
        <Steps current={0} style={{ marginBottom: 24 }}>
          <Steps.Step title="上传报告"/><Steps.Step title="审核编辑"/><Steps.Step title="导出Word"/>
        </Steps>

        <Alert type="info" message="支持美亚手机大师 FL-901V5 生成的 HTML 报告"
          description="可选择文件夹上传（含压缩选项）或直接上传 .rar/.zip 压缩包"
          style={{ marginBottom: 16 }} />

        <Radio.Group value={uploadMode} onChange={e => onModeChange(e.target.value)}
          style={{ marginBottom: 16 }}>
          <Radio.Button value="folder">选择文件夹</Radio.Button>
          <Radio.Button value="archive">上传压缩包</Radio.Button>
        </Radio.Group>

        {uploadMode === 'folder' ? (
          <>
            <Checkbox checked={compress} onChange={e => onCompressChange(e.target.checked)}
              style={{ marginBottom: 12, display: 'block' }}>
              压缩为 .rar
            </Checkbox>
            <Button type="primary" size="large" icon={<UploadOutlined />}
              onClick={onFolderUpload} loading={parsing} block>
              选择报告目录并解析
            </Button>
          </>
        ) : (
          <Dragger accept=".rar,.zip" showUploadList={false}
            beforeUpload={handleArchive} disabled={parsing}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽压缩包到此区域上传</p>
            <p className="ant-upload-hint">支持 .rar 和 .zip 格式，最大 500MB</p>
          </Dragger>
        )}

        {result && <FileInfoCard rarInfo={result.rar_info} />}
      </Card>
    </div>
  )
}
