import React, { useEffect, useMemo, useState } from 'react'
import { Button, Layout, Menu, Tooltip } from 'antd'
import {
  ApartmentOutlined,
  AppstoreOutlined,
  CompassOutlined,
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
const moreCapabilitiesKey = 'more-capabilities'

interface PlatformSidebarProps {
  collapsed: boolean
  onToggle: () => void
}

function moreCapabilitiesTitle() {
  return <span className="platform-sidebar__unavailable"><span>更多能力</span><small>即将开放</small></span>
}

function navigationIcon(collapsed: boolean, label: string, icon: React.ReactElement) {
  if (!collapsed) return icon
  return (
    <span className="platform-sidebar__nav-icon" role="img" aria-label={label}>
      <Tooltip title={label} placement="right" mouseEnterDelay={0.2}>
        <span aria-hidden="true">{icon}</span>
      </Tooltip>
    </span>
  )
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
    const submenuTitle = target?.closest('.ant-menu-submenu-title')
    const isModuleTitle = Boolean(submenuTitle?.querySelector('a[href="/electronic-inspection/workbench"]'))
    if ((event.key === 'Enter' || event.key === ' ') && target
      && submenuTitle && isModuleTitle
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
    if (location.pathname === '/electronic-inspection') return 'electronic-inspection-workbench'
    if (location.pathname === '/electronic-inspection/workbench'
      || location.pathname.startsWith('/electronic-inspection/cases/')
      || location.pathname === '/electronic-inspection/generate' || location.pathname === '/generate') {
      return 'electronic-inspection-workbench'
    }
    if (isModulePath) return moduleKey
    return 'home'
  }, [isModulePath, location.pathname])

  const brandMark = <span className="platform-sidebar__brand-mark">文</span>

  return (
    <Sider className="platform-sidebar" width={240} collapsedWidth={80} collapsed={collapsed} trigger={null}>
      <div className="platform-sidebar__brand">
        {collapsed
          ? <Tooltip title="笔录自检平台（文枢）" placement="right" mouseEnterDelay={0.2}>{brandMark}</Tooltip>
          : <>{brandMark}<span>笔录自检平台（文枢）</span></>}
      </div>
      <Menu theme="light" mode="inline" inlineCollapsed={collapsed} selectedKeys={[selectedKey]}
        triggerSubMenuAction={collapsed ? 'click' : 'hover'} openKeys={openKeys}
        onOpenChange={keys => setOpenKeys(keys as string[])} onKeyDown={handleMenuKeyDown}>
        <Menu.Item key="home" aria-label="首页" icon={navigationIcon(collapsed, '首页', <HomeOutlined />)}
          title={collapsed ? false : '首页'}>
          <Link to="/">首页</Link>
        </Menu.Item>
        <Menu.SubMenu key={moduleKey} aria-label="电子数据检查笔录"
          icon={navigationIcon(collapsed, '电子数据检查笔录', <FileTextOutlined />)} title={
          <Link to="/electronic-inspection/workbench" onClick={event => event.stopPropagation()}>电子数据检查笔录</Link>
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
        <Menu.SubMenu key={moreCapabilitiesKey} aria-label="更多能力"
          icon={navigationIcon(collapsed, '更多能力', <CompassOutlined />)} title={moreCapabilitiesTitle()}>
          <Menu.Item key="professional-report" icon={<FileSearchOutlined />} disabled title="专业化勘查报告（即将开放）">
            专业化勘查报告
          </Menu.Item>
          <Menu.Item key="digital-forensic" icon={<ApartmentOutlined />} disabled title="电子数据鉴定文书（即将开放）">
            电子数据鉴定文书
          </Menu.Item>
          <Menu.Item key="scene-triple" icon={<FileTextOutlined />} disabled title="传统现场三录（即将开放）">
            传统现场三录
          </Menu.Item>
          <Menu.Item key="scene-inspection" icon={<FileSearchOutlined />} disabled title="传统现场检查笔录（即将开放）">
            传统现场检查笔录
          </Menu.Item>
          <Menu.Item key="forensic-medical" icon={<SafetyCertificateOutlined />} disabled title="法医鉴定文书自检（即将开放）">
            法医鉴定文书自检
          </Menu.Item>
        </Menu.SubMenu>
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
