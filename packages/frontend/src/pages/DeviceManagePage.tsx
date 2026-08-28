// 第 12 层：FE_Pages — 硬件设备管理页面

import { Typography } from 'antd'
import { SettingOutlined } from '@ant-design/icons'
import DeviceManager from '../components/DeviceManager'

const { Title } = Typography

export default function DeviceManagePage() {
  return (
    <div className="platform-page platform-device-page">
      <Title level={3}><SettingOutlined /> 取证硬件设备管理</Title>
      <DeviceManager />
    </div>
  )
}
