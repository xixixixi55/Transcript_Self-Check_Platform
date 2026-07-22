// Layer 11: FE_Components — 报告上传步骤
// 提取自 RecordGeneratePage 以控制文件大小
import React from 'react'
import { Button, Card, Radio, Steps, Typography, Alert, Upload, message } from 'antd'
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
  parsing: boolean
  result: ParseReportResponse | null
  error?: string | null
  errorCode?: string | null
  onFolderUpload: () => void
  onArchiveUpload: (file: File) => Promise<boolean>
  onClearReportCache: () => Promise<unknown>
  clearingCache: boolean
  cacheClearMessage?: string | null
  cacheClearError?: string | null
}

export default function ReportUploadStep({
  uploadMode, onModeChange,
  parsing, result, error, errorCode, onFolderUpload, onArchiveUpload,
  onClearReportCache, clearingCache, cacheClearMessage, cacheClearError,
}: Props) {
  const handleArchive = async (file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!SUPPORTED_ARCHIVE_FORMATS.includes(ext)) {
      message.error('仅支持 .rar 和 .zip 格式的压缩包')
      return false
    }
    return onArchiveUpload(file)
  }

  const handleClearReportCache = () => {
    if (clearingCache) return
    const confirmed = window.confirm('确定清空全部解析缓存吗？清空后下次需要重新解析报告。')
    if (confirmed) void onClearReportCache()
  }

  return (
    <div style={{ padding: 48, maxWidth: 800, margin: '0 auto' }}>
      <Card>
        {error && <Alert
          type="error"
          message={errorCode ? `${errorCode}: ${error}` : error}
          showIcon
          style={{ marginBottom: 16 }}
        />}
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

        <div style={{ marginBottom: 16 }}>
          <Button
            onClick={handleClearReportCache}
            loading={clearingCache}
            disabled={parsing || clearingCache}
          >
            清空解析缓存
          </Button>
        </div>
        {cacheClearMessage && <Alert
          type="success"
          message={cacheClearMessage}
          showIcon
          style={{ marginBottom: 16 }}
        />}
        {cacheClearError && <Alert
          type="error"
          message={cacheClearError}
          action={<Button size="small" onClick={handleClearReportCache}>重试</Button>}
          showIcon
          style={{ marginBottom: 16 }}
        />}

        {uploadMode === 'folder' ? (
          <>
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
