import React, { useEffect, useMemo, useState } from 'react'
import { Button, Layout, Menu, Tooltip } from 'antd'
import {
  ApartmentOutlined,
  AppstoreOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  HomeOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { Link, useLocation } from 'react-router-dom'

const { Sider } = Layout
const moduleKey = 'electronic-inspection'

interface PlatformSidebarProps {
  collapsed: boolean
  onToggle: () => void
}

function unavailableLabel(label: string) {
  return <span className="platform-sidebar__unavailable"><span>{label}</span><small>暂未开放</small></span>
}

export function PlatformSidebar({ collapsed, onToggle }: PlatformSidebarProps) {
  const location = useLocation()
  const isModulePath = location.pathname.startsWith('/electronic-inspection')
    || location.pathname === '/generate' || location.pathname === '/devices'
    || location.pathname === '/inspectors' || location.pathname === '/templates'
  const [openKeys, setOpenKeys] = useState<string[]>(isModulePath ? [moduleKey] : [])

  useEffect(() => {
    if (isModulePath) setOpenKeys(keys => keys.includes(moduleKey) ? keys : [...keys, moduleKey])
  }, [isModulePath])

  const toggleModuleMenu = () => setOpenKeys(keys => keys.includes(moduleKey)
    ? keys.filter(key => key !== moduleKey) : [...keys, moduleKey])
  const handleMenuKeyDown = (event: React.KeyboardEvent) => {
    const target = event.target instanceof Element ? event.target : null
    if ((event.key === 'Enter' || event.key === ' ') && target
      && target.closest('.ant-menu-submenu-title')
      && !target.closest('.ant-menu-submenu-title a')) {
      event.preventDefault(); event.stopPropagation(); toggleModuleMenu()
    }
  }

  const selectedKey = useMemo(() => {
    if (location.pathname === '/electronic-inspection/devices' || location.pathname === '/devices') {
      return 'electronic-inspection-devices'
    }
    if (location.pathname === '/electronic-inspection/inspectors' || location.pathname === '/inspectors') {
      return 'electronic-inspection-inspectors'
    }
    if (location.pathname === '/electronic-inspection/templates' || location.pathname === '/templates') {
      return 'electronic-inspection-templates'
    }
    if (location.pathname === '/electronic-inspection') return moduleKey
    if (location.pathname === '/electronic-inspection/workbench'
      || location.pathname.startsWith('/electronic-inspection/cases/')
      || location.pathname === '/electronic-inspection/generate' || location.pathname === '/generate') {
      return 'electronic-inspection-workbench'
    }
    if (isModulePath) return moduleKey
    return 'home'
  }, [isModulePath, location.pathname])

  return (
    <Sider className="platform-sidebar" width={240} collapsedWidth={64} collapsed={collapsed} trigger={null}>
      <div className="platform-sidebar__brand"><span className="platform-sidebar__brand-mark">文</span>{!collapsed && <span>笔录自检平台（文枢）</span>}</div>
      <Menu theme="dark" mode="inline" inlineCollapsed={collapsed} selectedKeys={[selectedKey]}
        openKeys={openKeys} onOpenChange={keys => setOpenKeys(keys as string[])} onKeyDown={handleMenuKeyDown}>
        <Menu.Item key="home" icon={<HomeOutlined />} title="首页"><Link to="/">首页</Link></Menu.Item>
        <Menu.SubMenu key={moduleKey} icon={<FileTextOutlined />} title={
          <Link to="/electronic-inspection" onClick={event => event.stopPropagation()}>电子数据检查笔录</Link>
        }>
          <Menu.Item key="electronic-inspection-workbench" icon={<AppstoreOutlined />} title="案件工作台">
            <Link to="/electronic-inspection/workbench">案件工作台</Link>
          </Menu.Item>
          <Menu.Item key="electronic-inspection-devices" title="电子设备管理">
            <Link to="/electronic-inspection/devices">电子设备管理</Link>
          </Menu.Item>
          <Menu.Item key="electronic-inspection-inspectors" title="检查人员管理">
            <Link to="/electronic-inspection/inspectors">检查人员管理</Link>
          </Menu.Item>
          <Menu.Item key="electronic-inspection-templates" title="笔录模版管理">
            <Link to="/electronic-inspection/templates">笔录模版管理</Link>
          </Menu.Item>
        </Menu.SubMenu>
        <Menu.Item key="professional-report" icon={<FileSearchOutlined />} disabled title="专业化勘查报告（暂未开放）">
          {unavailableLabel('专业化勘查报告')}
        </Menu.Item>
        <Menu.Item key="digital-forensic" icon={<ApartmentOutlined />} disabled title="电子数据鉴定文书（暂未开放）">
          {unavailableLabel('电子数据鉴定文书')}
        </Menu.Item>
        <Menu.Item key="scene-triple" icon={<FileTextOutlined />} disabled title="传统现场三录（暂未开放）">
          {unavailableLabel('传统现场三录')}
        </Menu.Item>
        <Menu.Item key="scene-inspection" icon={<FileSearchOutlined />} disabled title="传统现场检查笔录（暂未开放）">
          {unavailableLabel('传统现场检查笔录')}
        </Menu.Item>
        <Menu.Item key="forensic-medical" icon={<SafetyCertificateOutlined />} disabled title="法医鉴定文书自检（暂未开放）">
          {unavailableLabel('法医鉴定文书自检')}
        </Menu.Item>
      </Menu>
      <div className="platform-sidebar__footer">
        <Tooltip title={collapsed ? '展开导航' : '收起导航'} placement="right">
          <Button type="text" aria-label={collapsed ? '展开导航' : '收起导航'}
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={onToggle} />
        </Tooltip>
      </div>
    </Sider>
  )
}
