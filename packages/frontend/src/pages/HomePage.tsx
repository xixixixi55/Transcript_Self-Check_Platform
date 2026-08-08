// Layer 12: FE_Pages — 平台首页

import { Button, Card, Col, Row, Typography } from 'antd'
import {
  ApartmentOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'

const { Paragraph, Text, Title } = Typography

const featureItems = [
  { icon: FileTextOutlined, title: '电子数据检查笔录', description: '上传检查报告，核对并编辑文书内容，导出 Word 笔录。', available: true },
  { icon: FileSearchOutlined, title: '专业化勘查报告', description: '该功能暂未开放', available: false },
  { icon: ApartmentOutlined, title: '电子数据鉴定文书', description: '该功能暂未开放', available: false },
  { icon: FileTextOutlined, title: '传统现场三录', description: '该功能暂未开放', available: false },
  { icon: FileSearchOutlined, title: '传统现场检查笔录', description: '该功能暂未开放', available: false },
  { icon: SafetyCertificateOutlined, title: '法医鉴定文书自检', description: '该功能暂未开放', available: false },
]

export default function HomePage() {
  return (
    <div className="platform-page platform-home">
      <div className="platform-home__heading">
        <div className="platform-page__eyebrow">平台首页</div>
        <Title level={1}>电子数据检查文书辅助平台</Title>
        <Paragraph className="platform-page__description">
          用于电子数据检查笔录及相关文书的生成、审核与导出。
        </Paragraph>
      </div>

      <section aria-labelledby="platform-features-title">
        <Title level={2} id="platform-features-title" className="platform-home__section-title">核心功能</Title>
        <Row gutter={[16, 16]}>
          {featureItems.map(({ icon: Icon, title, description, available }) => {
            const card = (
              <Card
                className={`platform-feature-card ${available ? 'platform-feature-card--available' : 'platform-feature-card--unavailable'}`}
                bordered
              >
                <Icon className="platform-feature-card__icon" />
                <Title level={3}>{title}</Title>
                <Paragraph>{description}</Paragraph>
                {available ? <Button type="primary">进入功能</Button> : <Text className="platform-feature-card__status">暂未开放</Text>}
              </Card>
            )
            return (
              <Col key={title} xs={24} sm={12} lg={8}>
                {available ? <Link to="/electronic-inspection/workbench" className="platform-feature-card__link">{card}</Link> : card}
              </Col>
            )
          })}
        </Row>
      </section>
    </div>
  )
}
