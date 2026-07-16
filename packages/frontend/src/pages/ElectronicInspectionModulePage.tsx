import React from 'react'
import { Button, Card, Col, Row, Typography } from 'antd'
import { DatabaseOutlined, FileTextOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'

const { Paragraph, Title } = Typography

export default function ElectronicInspectionModulePage() {
  return (
    <div className="platform-page platform-module-page">
      <div className="platform-page__eyebrow">业务模块</div>
      <Title level={1}>电子数据检查笔录</Title>
      <Paragraph className="platform-page__description">
        完成检查报告上传、解析、内容审核和电子数据检查笔录导出。
      </Paragraph>
      <Row gutter={[16, 16]} className="platform-module-page__entries">
        <Col xs={24} md={12}>
          <Card className="platform-entry-card" bordered>
            <FileTextOutlined className="platform-entry-card__icon" />
            <Title level={3}>生成笔录</Title>
            <Paragraph>上传检查报告，解析并审核内容，导出电子数据检查笔录。</Paragraph>
            <Link to="/electronic-inspection/generate">
              <Button type="primary">进入生成笔录</Button>
            </Link>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card className="platform-entry-card" bordered>
            <DatabaseOutlined className="platform-entry-card__icon" />
            <Title level={3}>电子设备管理</Title>
            <Paragraph>维护生成笔录过程中使用的电子设备信息。</Paragraph>
            <Link to="/electronic-inspection/devices">
              <Button>进入设备管理</Button>
            </Link>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
