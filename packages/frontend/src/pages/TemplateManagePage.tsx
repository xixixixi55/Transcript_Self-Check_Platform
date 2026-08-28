// 第 12 层：FE_Pages — 笔录模版管理页面。
import { FileTextOutlined } from '@ant-design/icons'
import { Typography } from 'antd'
import TemplateManager from '../components/TemplateManager'

const { Title } = Typography

export default function TemplateManagePage() {
  return (
    <div className="platform-page platform-template-page">
      <Title level={3}><FileTextOutlined /> 笔录模版管理</Title>
      <TemplateManager />
    </div>
  )
}
