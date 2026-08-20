// Layer 11: FE_Components — validated preview archive facts and downloads.
import React from 'react'
import { Alert, Button, Card, Descriptions, Space, Tag, Typography } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { ArchiveLifecycleStatus, ArchiveManifest, ArchiveMedium, ArchiveTaskResult } from '@biji/shared/types'

const { Text } = Typography
const LABELS: Record<ArchiveLifecycleStatus, string> = {
  not_prepared: '归档尚未准备',
  preparing: '正在准备归档',
  ready: '归档已准备',
  idle: '等待开始',
  waiting: '等待开始',
  planning: '等待开始',
  blocked: '失败',
  compressing: '压缩中',
  validating: '完整性校验中',
  hashing: 'MD5计算中',
  completed: '已完成',
  failed: '失败',
}

interface Props {
  contextId: string | null
  status: ArchiveLifecycleStatus
  loading?: boolean
  onPrepare?: () => void
  manifest: ArchiveManifest | null
  resultParts?: ArchiveTaskResult['parts'] | null
  taskId?: string | null
  error: string | null
  showPartDownload?: boolean
  archiveMedium?: ArchiveMedium | null
}

interface DisplayPart {
  part_id: string
  part_number: number
  filename: string
  size_bytes: number
  md5: string
  disc_number: string
  disc_date: string
  disc_capacity_bytes?: number
}

function readableSize(bytes: number): string {
  const mb = bytes / 1_000_000
  return `${mb.toFixed(2)} MB（${bytes} 字节）`
}

export function ArchiveStatusCard({ contextId, status, loading = false, onPrepare = () => undefined,
  manifest, resultParts = null, taskId = null, error, showPartDownload = true, archiveMedium = null }: Props) {
  const parts: DisplayPart[] = manifest?.parts || resultParts?.map((part, index) => ({
    ...part, part_number: index + 1,
  })) || []
  const hardDrive = archiveMedium === 'hard_drive' || manifest?.archive_mode === 'oversized_single_volume'
  return (
    <Card size="small" title="真实 RAR 归档">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Tag color={status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'processing'}>
          {LABELS[status]}
        </Tag>
        {error && <Alert type={status === 'failed' ? 'error' : 'info'} message={error} showIcon />}
        {contextId && (status === 'not_prepared' || status === 'failed') && (
          <Button type="primary" loading={loading} onClick={onPrepare}>
            {status === 'failed' ? '重试归档准备' : '开始准备归档'}
          </Button>
        )}
        {parts.map(part => (
          <Card size="small" key={part.part_id}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="RAR文件名">{part.filename}</Descriptions.Item>
              <Descriptions.Item label="文件大小">{readableSize(part.size_bytes)}</Descriptions.Item>
              <Descriptions.Item label="MD5"><Text code>{part.md5.toUpperCase()}</Text></Descriptions.Item>
              <Descriptions.Item label="分卷序号">{part.part_number}</Descriptions.Item>
              <Descriptions.Item label={hardDrive ? '硬盘编号' : '光盘编号'}>{part.disc_number}</Descriptions.Item>
              {part.disc_capacity_bytes !== undefined && <Descriptions.Item label={hardDrive ? '硬盘容量' : '光盘容量'}>{readableSize(part.disc_capacity_bytes)}</Descriptions.Item>}
              <Descriptions.Item label="归档状态">已验证</Descriptions.Item>
            </Descriptions>
            {showPartDownload && (contextId || taskId) && (
              <Button
                icon={<DownloadOutlined />}
                href={contextId && manifest
                  ? API_ENDPOINTS.ARCHIVE_PART(contextId, manifest.manifest_id, part.part_id)
                  : taskId ? API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT_PART(taskId, part.part_id) : undefined}
                download={part.filename}
              >
                下载该 RAR
              </Button>
            )}
          </Card>
        ))}
      </Space>
    </Card>
  )
}
