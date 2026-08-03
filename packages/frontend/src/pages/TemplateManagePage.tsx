// Layer 12: FE_Pages — 笔录模版管理页面。
import { FileTextOutlined } from '@ant-design/icons'
import { Typography } from 'antd'
import TemplateManager from '../components/TemplateManager'

const { Title } = Typography

export default function TemplateManagePage() {
  return (
    <div className="platform-page platform-template-page">
      <Title level={3}><FileTextOutlined /> 笔录模版管理</Title>
      <p className="platform-page__description">管理可用于新案件和案件导出的已校验笔录模版版本。</p>
      <TemplateManager />
    </div>
  )
}
