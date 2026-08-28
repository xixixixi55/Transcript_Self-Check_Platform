// 第 12 层：FE_Pages — 检查人员管理页面
import { Typography } from 'antd'
import InspectorManager from '../components/InspectorManager'

const { Title } = Typography

export default function InspectorManagePage() {
  return (
    <div className="platform-management-page platform-inspector-page">
      <div className="platform-management-page__inner">
        <header className="platform-management-page__header">
          <div className="platform-page__eyebrow">电子数据检查笔录</div>
          <Title level={1}>检查人员管理</Title>
        </header>
        <InspectorManager />
      </div>
    </div>
  )
}
