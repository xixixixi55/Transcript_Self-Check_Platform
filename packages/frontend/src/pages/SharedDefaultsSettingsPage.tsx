// 第 12 层：FE_Pages — 集中的笔录默认设置页面。
import { Typography } from 'antd'
import { SharedDefaultsSettingsForm } from '../components/SharedDefaultsSettingsForm'

const { Title } = Typography

export function SharedDefaultsSettingsPage() {
  return (
    <div className="platform-management-page platform-shared-defaults-page">
      <div className="platform-management-page__inner">
        <header className="platform-management-page__header">
          <div className="platform-page__eyebrow">电子数据检查笔录</div>
          <Title level={1}>笔录默认设置</Title>
        </header>
        <SharedDefaultsSettingsForm />
      </div>
    </div>
  )
}
