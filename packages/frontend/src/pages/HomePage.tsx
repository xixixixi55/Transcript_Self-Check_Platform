// Layer 12: FE_Pages — 首页

import { Card, Typography, Space } from 'antd'
import { FileTextOutlined, SearchOutlined, EditOutlined } from '@ant-design/icons'
import { RECORD_TYPE_LABELS } from '@biji/shared/constants'
import { RecordType } from '@biji/shared/types'

const { Title, Paragraph } = Typography

const features = [
  { icon: <FileTextOutlined />, title: '电子数据检查笔录', desc: '自动生成，优先实现', type: RecordType.ELECTRONIC_INSPECTION },
  { icon: <SearchOutlined />, title: '专业化勘查报告', desc: '自动生成', type: RecordType.FORENSIC_REPORT },
  { icon: <EditOutlined />, title: '人工调节修改', desc: '支持在线编辑和预览' },
]

export default function HomePage() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <Title level={2}>欢迎使用笔录自检平台</Title>
      <Paragraph type="secondary">
        支持 6 类电子数据文书的自动生成、人工调节和归档管理，面向民警使用。
      </Paragraph>

      <Title level={4} style={{ marginTop: 32 }}>支持的文书类型</Title>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {Object.entries(RECORD_TYPE_LABELS).map(([key, label]) => (
          <Card key={String(key)} size="small" hoverable>
            <strong>{String(label)}</strong>
            {key === RecordType.ELECTRONIC_INSPECTION && (
              <span style={{ color: '#1890ff', marginLeft: 8 }}>← 优先实现</span>
            )}
          </Card>
        ))}
      </Space>
    </div>
  )
}
