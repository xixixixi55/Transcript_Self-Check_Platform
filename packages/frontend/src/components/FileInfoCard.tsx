// Layer 11: FE_Components — 文件信息卡片
// REQ-015: 上传后展示 MD5 哈希值和文件大小（MB）
import React from 'react'
import { Card, Descriptions, Typography } from 'antd'
import { FileProtectOutlined } from '@ant-design/icons'
import type { RarInfo } from '@biji/shared/types'

const { Text } = Typography

interface FileInfoCardProps {
  rarInfo: RarInfo | null
}

function formatFileSize(sizeDisplay: string): string {
  if (!sizeDisplay) return 'N/A'
  // size_display 已是后端格式化后的字符串（如 "11.77 MB"），直接返回
  return sizeDisplay
}

export default function FileInfoCard({ rarInfo }: FileInfoCardProps) {
  if (!rarInfo) {
    return (
      <Card size="small" style={{ marginTop: 16 }}>
        <Text type="secondary">未生成压缩文件</Text>
      </Card>
    )
  }

  return (
    <Card
      size="small"
      title={<><FileProtectOutlined /> 文件信息</>}
      style={{ marginTop: 16 }}
    >
      <Descriptions column={1} size="small">
        <Descriptions.Item label="文件 MD5">
          <Text code style={{ fontSize: 12, wordBreak: 'break-all' }}>
            {rarInfo.md5.toUpperCase()}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label="文件大小">
          {formatFileSize(rarInfo.size_display)}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  )
}
