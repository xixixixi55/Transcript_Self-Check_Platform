import React, { useState } from 'react'
import { ConfigProvider } from 'antd'
import { useLocation } from 'react-router-dom'
import { PlatformSidebar } from './PlatformSidebar'
import '../platformShell.css'
import '../reviewWorkspace.css'

function getContextTitle(pathname: string): string {
  if (pathname.startsWith('/electronic-inspection')) return '电子数据检查笔录'
  return '平台首页'
}

export function PlatformShell({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <ConfigProvider theme={{
      token: {
        colorPrimary: '#2F6FA3',
        colorInfo: '#3B78A8',
        borderRadius: 6,
        fontFamily: 'Microsoft YaHei UI, Microsoft YaHei, Segoe UI, sans-serif',
      },
    }}>
      <div className={`platform-shell ${collapsed ? 'platform-shell--collapsed' : ''}`}>
        <PlatformSidebar collapsed={collapsed} onToggle={() => setCollapsed(value => !value)} />
        <div className="platform-shell__main">
          <header className="platform-shell__topbar">
            <span className="platform-shell__topbar-context">笔录自检平台（文枢）</span>
            <span className="platform-shell__topbar-title">{getContextTitle(location.pathname)}</span>
          </header>
          <main className="platform-shell__content">{children}</main>
        </div>
      </div>
    </ConfigProvider>
  )
}
