import React from 'react'
import { Button, Card, Col, Row, Typography } from 'antd'
import { AppstoreOutlined, DatabaseOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { DemoReadinessNotice } from '../components/DemoReadinessNotice'

const { Paragraph, Title } = Typography

export default function ElectronicInspectionModulePage() {
  return (
    <div className="platform-page platform-module-page">
      <div className="platform-page__eyebrow">业务模块</div>
      <Title level={1}>电子数据检查笔录</Title>
      <Paragraph className="platform-page__description">
        案件工作台是电子数据检查笔录的统一生产入口，负责案件登记、解析、审核、保存和导出。
      </Paragraph>
      <DemoReadinessNotice />
      <Row gutter={[16, 16]} className="platform-module-page__entries">
        <Col xs={24} md={12}>
          <Card className="platform-entry-card" bordered>
            <AppstoreOutlined className="platform-entry-card__icon" />
            <Title level={3}>案件工作台</Title>
            <Paragraph>查看多个案件的解析状态，切换案件并恢复已保存的完整审核草稿。</Paragraph>
            <Link to="/electronic-inspection/workbench"><Button type="primary">进入案件工作台</Button></Link>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card className="platform-entry-card" bordered>
            <DatabaseOutlined className="platform-entry-card__icon" />
            <Title level={3}>电子设备管理</Title>
            <Paragraph>维护生成笔录过程中使用的电子设备信息。</Paragraph>
            <Link to="/electronic-inspection/devices"><Button>进入设备管理</Button></Link>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
