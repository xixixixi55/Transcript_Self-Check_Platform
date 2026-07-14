// Layer 12: FE_Pages — 硬件设备管理页面
import React from 'react'
import { Layout, Typography } from 'antd'
import { SettingOutlined } from '@ant-design/icons'
import DeviceManager from '../components/DeviceManager'

const { Title } = Typography

export default function DeviceManagePage() {
  return (
    <Layout.Content style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <Title level={3}><SettingOutlined /> 取证硬件设备管理</Title>
      <p style={{ color: '#999', marginBottom: 24 }}>
        管理取证硬件设备清单，生成笔录时可选硬件设备。
      </p>
      <DeviceManager />
    </Layout.Content>
  )
}
