// 第 12 层：FE_Pages — 笔录模版管理页面。
import { Typography } from 'antd'
import TemplateManager from '../components/TemplateManager'

const { Title } = Typography

export default function TemplateManagePage() {
  return (
    <div className="platform-management-page platform-template-page">
      <div className="platform-management-page__inner">
        <header className="platform-management-page__header">
          <div className="platform-page__eyebrow">电子数据检查笔录</div>
          <Title level={1}>笔录模版管理</Title>
        </header>
        <TemplateManager />
      </div>
    </div>
  )
}
