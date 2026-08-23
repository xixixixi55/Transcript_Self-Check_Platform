// Layer 12: FE_Pages — centralized record-default settings page.
import { SettingOutlined } from '@ant-design/icons'
import { Typography } from 'antd'
import { SharedDefaultsSettingsForm } from '../components/SharedDefaultsSettingsForm'

const { Title } = Typography

export function SharedDefaultsSettingsPage() {
  return (
    <div className="platform-page platform-shared-defaults-page">
      <Title level={3}><SettingOutlined /> 笔录默认设置</Title>
      <SharedDefaultsSettingsForm />
    </div>
  )
}
