// Layer 12: FE_Pages — 应用路由定义

import { Routes, Route, Navigate, Link } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import { HomeOutlined, FileTextOutlined, SettingOutlined } from '@ant-design/icons'
import HomePage from './pages/HomePage'
import RecordGeneratePage from './pages/RecordGeneratePage'
import DeviceManagePage from './pages/DeviceManagePage'

const { Header, Content, Footer } = Layout

export default function App() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <span style={{ color: '#fff', fontSize: 18, fontWeight: 'bold', marginRight: 32 }}>
          笔录自检平台（文枢）
        </span>
        <Menu theme="dark" mode="horizontal" selectable={false}
          items={[
            { key: 'home', icon: <HomeOutlined />, label: <Link to="/">首页</Link> },
            { key: 'generate', icon: <FileTextOutlined />, label: <Link to="/generate">生成笔录</Link> },
            { key: 'devices', icon: <SettingOutlined />, label: <Link to="/devices">设备管理</Link> },
          ]}
        />
      </Header>
      <Content style={{ padding: 24 }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/generate" element={<RecordGeneratePage />} />
          <Route path="/devices" element={<DeviceManagePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        笔录自检平台 ©{new Date().getFullYear()} — 内部使用
      </Footer>
    </Layout>
  )
}
