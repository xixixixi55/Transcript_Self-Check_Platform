// 第 12 层：FE_Pages — 硬件设备管理页面

import { Typography } from 'antd'
import DeviceManager from '../components/DeviceManager'

const { Title } = Typography

export default function DeviceManagePage() {
  return (
    <div className="platform-management-page platform-device-page">
      <div className="platform-management-page__inner">
        <header className="platform-management-page__header">
          <div className="platform-page__eyebrow">电子数据检查笔录</div>
          <Title level={1}>取证硬件设备管理</Title>
        </header>
        <DeviceManager />
      </div>
    </div>
  )
}
