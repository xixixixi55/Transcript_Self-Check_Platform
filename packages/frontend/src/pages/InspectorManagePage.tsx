// 第 12 层：FE_Pages — 检查人员管理页面
import { TeamOutlined } from '@ant-design/icons'
import { Typography } from 'antd'
import InspectorManager from '../components/InspectorManager'

const { Title } = Typography

export default function InspectorManagePage() {
  return (
    <div className="platform-page platform-inspector-page">
      <Title level={3}><TeamOutlined /> 检查人员管理</Title>
      <InspectorManager />
    </div>
  )
}
