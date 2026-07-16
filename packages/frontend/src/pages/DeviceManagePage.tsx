// Layer 12: FE_Pages — 硬件设备管理页面

import { Typography } from 'antd'
import { SettingOutlined } from '@ant-design/icons'
import DeviceManager from '../components/DeviceManager'

const { Title } = Typography

export default function DeviceManagePage() {
  return (
    <div className="platform-page platform-device-page">
      <Title level={3}><SettingOutlined /> 取证硬件设备管理</Title>
      <p className="platform-page__description platform-device-page__description">
        管理取证硬件设备清单，生成笔录时可选硬件设备。
      </p>
      <DeviceManager />
    </div>
  )
}
