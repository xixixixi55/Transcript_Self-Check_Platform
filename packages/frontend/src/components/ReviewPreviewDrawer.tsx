import React from 'react'
import { Alert, Descriptions, Drawer, Typography } from 'antd'
import type { InspectionReport } from '@biji/shared/types'

const { Paragraph, Text, Title } = Typography

interface ReviewPreviewDrawerProps {
  open: boolean
  report: InspectionReport
  onClose: () => void
}

export function ReviewPreviewDrawer({ open, report, onClose }: ReviewPreviewDrawerProps) {
  const attachments = report.attachments
  const photoCount = attachments?.photo_ids?.length || 0
  const extractCount = attachments?.extract_list?.rows?.length || 0
  const sectionItems = ['一、绪论', '二、检查', '附件']

  return (
    <Drawer
      title="报告结构摘要预览"
      placement="right"
      open={open}
      width={560}
      onClose={onClose}
      keyboard={false}
      destroyOnClose={false}
      getContainer={false}
      rootStyle={{ position: 'absolute' }}
      className="review-preview-drawer"
    >
      <Alert
        type="info"
        showIcon
        message="非最终 Word 版式预览"
        description="此处仅用于核对报告结构、案件信息和附件数量，不代表最终 Word 的分页、样式、VML 或空白页结果。"
      />
      <Title level={4}>案件基本信息</Title>
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="文书名称">{report.title || '未填写'}</Descriptions.Item>
        <Descriptions.Item label="文号">{report.document_number || '未填写'}</Descriptions.Item>
        <Descriptions.Item label="案件编号">{report.case_number || '未识别'}</Descriptions.Item>
        <Descriptions.Item label="案件摘要">{report.introduction?.case_summary || '未填写'}</Descriptions.Item>
      </Descriptions>
      <Title level={4}>章节目录</Title>
      <ol className="review-preview-drawer__outline">
        {sectionItems.map(item => <li key={item}>{item}</li>)}
      </ol>
      <Title level={4}>附件摘要</Title>
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="附件 1 提取清单">{extractCount} 行</Descriptions.Item>
        <Descriptions.Item label="附件 2 检材照片">{photoCount} 张</Descriptions.Item>
        <Descriptions.Item label="附件 3 光盘编号">{attachments?.disc_number || '未填写'}</Descriptions.Item>
      </Descriptions>
      <Paragraph className="review-preview-drawer__note">
        <Text type="secondary">关闭预览后，主编辑区滚动位置保持不变。</Text>
      </Paragraph>
    </Drawer>
  )
}
