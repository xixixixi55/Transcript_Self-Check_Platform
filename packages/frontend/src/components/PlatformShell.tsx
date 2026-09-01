import React, { useState } from 'react'
import { ConfigProvider } from 'antd'
import { PlatformSidebar } from './PlatformSidebar'
import '../platformShell.css'
import '../reviewWorkspace.css'

export function PlatformShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(true)

  return (
    <ConfigProvider theme={{
      token: {
        colorPrimary: '#4E3FA8',
        colorPrimaryHover: '#3E53B9',
        colorInfo: '#3B78A8',
        borderRadius: 8,
        fontFamily: 'Microsoft YaHei UI, Microsoft YaHei, Segoe UI, sans-serif',
      },
    }}>
      <div className={`platform-shell ${collapsed ? 'platform-shell--collapsed' : ''}`}>
        <PlatformSidebar collapsed={collapsed} onToggle={() => setCollapsed(value => !value)} />
        <div className="platform-shell__main">
          <main className="platform-shell__content">{children}</main>
        </div>
      </div>
    </ConfigProvider>
  )
}
