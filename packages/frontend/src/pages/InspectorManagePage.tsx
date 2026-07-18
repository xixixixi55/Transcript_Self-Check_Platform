// Layer 12: FE_Pages — 检查人员管理页面
import { TeamOutlined } from '@ant-design/icons'
import { Typography } from 'antd'
import InspectorManager from '../components/InspectorManager'

const { Title } = Typography

export default function InspectorManagePage() {
  return (
    <div className="platform-page platform-inspector-page">
      <Title level={3}><TeamOutlined /> 检查人员管理</Title>
      <p className="platform-page__description">维护当前可选择的检查人员；报告保存的是独立快照。</p>
      <InspectorManager />
    </div>
  )
}
