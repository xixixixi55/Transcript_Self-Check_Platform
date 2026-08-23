// Layer 12: FE_Pages — centralized record-default settings page.
import { SettingOutlined } from '@ant-design/icons'
import { Typography } from 'antd'
import { SharedDefaultsSettingsForm } from '../components/SharedDefaultsSettingsForm'

const { Title, Paragraph } = Typography

export function SharedDefaultsSettingsPage() {
  return (
    <div className="platform-page platform-shared-defaults-page">
      <Title level={3}><SettingOutlined /> 笔录默认设置</Title>
      <Paragraph className="platform-shared-defaults-page__description">
        集中维护新案件可复用的默认内容。保存后不会修改已经创建的案件。
      </Paragraph>
      <SharedDefaultsSettingsForm />
    </div>
  )
}
